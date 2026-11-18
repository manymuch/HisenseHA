"""Data update coordinator for Hisense devices."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_ENABLE_WASHER_POLL,
    CONF_WASHER_POLL_INTERVAL,
    DEFAULT_ENABLE_WASHER_POLL,
    DEFAULT_WASHER_POLL_INTERVAL,
    MIN_WASHER_POLL_INTERVAL,
)
from .pyhisenseapi import HiSenseAC, HiSenseDryer, HiSenseFridge, HiSenseWasher


_LOGGER = logging.getLogger(__name__)
_CONTROL_REFRESH_DELAY = 1.0
_RETRY_DELAY = 60.0
_MAX_ATTEMPTS = 3

#: 冰箱定时轮询间隔（秒）。
_FRIDGE_SCAN_INTERVAL = 60
#: 洗衣机/干衣机/空调遵循纯事件驱动（不主动轮询，防止频繁请求导致封号），完全依赖 MQTT 实时推送与操作回读。



class HisenseDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch one device on demand and recover account access after failures."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: HiSenseAC | HiSenseDryer | HiSenseFridge | HiSenseWasher,
        device_type: str = "空调",
        entry=None,
    ) -> None:
        self.client = client
        self.device_type = device_type
        self._entry = entry
        self._refresh_task: asyncio.Task | None = None
        #: 上一次成功读到云端数据的本地时刻。设备自己报的 ``reportTime``
        #: 缺失时（少数机型）用它兜底，让「上次数据更新时间」实体始终有值。
        self.last_success_time: datetime | None = None
        self.last_push: dict[str, Any] | None = None
        self.push_history: list[dict[str, Any]] = []
        self._was_running = False
        self._countdown_task: asyncio.Task | None = None
        self._estimated_end_time: datetime | None = None

        initial_interval = (
            timedelta(seconds=_FRIDGE_SCAN_INTERVAL)
            if device_type == "冰箱"
            else None
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.device_id}",
            update_interval=initial_interval,
        )
        # No first refresh has completed; HA's coordinator defaults this to True.
        self.last_update_success = False

    async def _read_status(self) -> dict[str, Any] | None:
        """Read device state, keeping optional energy data best effort."""
        status = await self.client.check_status()
        if status and self.device_type == "空调" and hasattr(self.client, "get_energy"):
            try:
                energy_status = await self.client.get_energy()
            except Exception:
                _LOGGER.debug("Hisense energy read failed", exc_info=True)
                energy_status = None
            if energy_status:
                status = energy_status
        if status:
            self.last_success_time = dt_util.utcnow()
        return status

    async def _async_update_data(self) -> dict[str, Any]:
        """Try a fresh sign-in after a failed read, at most three times."""
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            request_token = self.client.access_token
            if request_token:
                try:
                    status = await self._read_status()
                except Exception:
                    _LOGGER.warning("Hisense %s status read failed", self.device_type, exc_info=True)
                    status = None
                if status:
                    self._adjust_poll_interval(status)
                    return status

            if not self.client.username or not self.client.password:
                raise UpdateFailed("Hisense AIHome credentials need reauthentication")

            if await self.client.refresh(force=True, previous_token=request_token):
                try:
                    status = await self._read_status()
                except Exception:
                    _LOGGER.warning("Hisense %s status retry failed", self.device_type, exc_info=True)
                    status = None
                if status:
                    self._adjust_poll_interval(status)
                    return status

            if attempt < _MAX_ATTEMPTS:
                _LOGGER.warning(
                    "Hisense %s status recovery attempt %s/%s failed; retrying in 60 seconds",
                    self.device_type, attempt, _MAX_ATTEMPTS,
                )
                await asyncio.sleep(_RETRY_DELAY)

        raise UpdateFailed(
            f"Failed to fetch Hisense {self.device_type} status after {_MAX_ATTEMPTS} attempts"
        )

    def async_start_refresh(self, *, delay: float = 0) -> None:
        """Coalesce manual and control-triggered refreshes into one task."""
        if self._refresh_task and not self._refresh_task.done():
            return
        coro = self._async_run_refresh(delay)
        if self._entry is not None:
            self._refresh_task = self._entry.async_create_background_task(
                self.hass, coro, f"{self.name} recovery"
            )
        elif hasattr(self.hass, "async_create_background_task"):
            self._refresh_task = self.hass.async_create_background_task(
                coro, f"{self.name} recovery"
            )
        else:
            self._refresh_task = self.hass.async_create_task(coro)

    async def async_request_refresh(self) -> None:
        """Route HA's generic entity update through the same recovery task."""
        self.async_start_refresh()

    async def _async_run_refresh(self, delay: float) -> None:
        try:
            if delay:
                await asyncio.sleep(delay)
            await self.async_refresh()
        finally:
            if self._refresh_task is asyncio.current_task():
                self._refresh_task = None

    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        """Update coordinator data and adjust dynamic polling interval."""
        if isinstance(data, dict):
            self._adjust_poll_interval(data)
        super().async_set_updated_data(data)

    def _start_app_countdown(self, status: dict[str, Any]) -> None:
        """Mimic Hisense App's _startTimeUpdateMode to run a smooth local countdown."""
        remain_mins = status.get("remaining_minutes")
        if remain_mins is None:
            val = status.get("remainRunTime")
            if val is None and isinstance(status.get("protocol_nonzero_values"), dict):
                val = status["protocol_nonzero_values"].get("remainRunTime")
            if val is not None and str(val).isdigit():
                remain_mins = int(val)

        if remain_mins and remain_mins > 0:
            self._estimated_end_time = dt_util.utcnow() + timedelta(minutes=remain_mins)
            if self._countdown_task is None or self._countdown_task.done():
                _LOGGER.debug(
                    "Starting App countdown timer for %s: %d minutes (est. finish %s)",
                    self.name,
                    remain_mins,
                    self._estimated_end_time,
                )
                self._countdown_task = self.hass.async_create_task(
                    self._async_countdown_loop()
                )

    def _stop_app_countdown(self) -> None:
        """Mimic Hisense App's _stopTimerUpdateMode to end the countdown."""
        if self._countdown_task and not self._countdown_task.done():
            self._countdown_task.cancel()
            _LOGGER.debug("Stopped App countdown timer for %s", self.name)
        self._countdown_task = None
        self._estimated_end_time = None

    async def _async_countdown_loop(self) -> None:
        """Local minute countdown ticker without querying cloud servers."""
        try:
            while True:
                await asyncio.sleep(60)
                if not self._estimated_end_time:
                    break
                now = dt_util.utcnow()
                diff_secs = (self._estimated_end_time - now).total_seconds()
                if diff_secs <= 0:
                    _LOGGER.debug("App countdown completed for %s; requesting sync", self.name)
                    self.async_start_refresh()
                    break

                mins_left = max(1, int(diff_secs / 60))
                if self.data and isinstance(self.data, dict):
                    self.data["remaining_minutes"] = mins_left
                    if isinstance(self.data.get("protocol_nonzero_values"), dict):
                        self.data["protocol_nonzero_values"]["remainRunTime"] = str(mins_left)
                    self.async_update_listeners()
        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.debug("Error in app countdown loop for %s: %s", self.name, err)
        finally:
            self._countdown_task = None

    def _adjust_poll_interval(self, status: dict[str, Any]) -> None:
        """Process status updates, manage App countdown timer, and adjust polling interval."""
        self._check_washer_completion(status)

        if self.device_type not in ("洗衣机", "干衣机"):
            return

        is_running = bool(status.get("is_running") or status.get("machine_state") == "running")
        is_complete = (
            status.get("machine_state") == "complete"
            or status.get("run_status") == 7
            or status.get("phase") == 7
        )

        if is_running and not is_complete:
            # 1. 启动类似海信 App 的本地倒计时模式 (_startTimeUpdateMode)
            self._start_app_countdown(status)

            # 2. 检查用户是否开启了洗涤中动态轮询
            options = self._entry.options if self._entry else {}
            enable_poll = options.get(CONF_ENABLE_WASHER_POLL, DEFAULT_ENABLE_WASHER_POLL)
            if enable_poll:
                poll_interval = options.get(CONF_WASHER_POLL_INTERVAL, DEFAULT_WASHER_POLL_INTERVAL)
                safe_interval = max(MIN_WASHER_POLL_INTERVAL, int(poll_interval))
                new_interval = timedelta(minutes=safe_interval)
                if self.update_interval != new_interval:
                    self.update_interval = new_interval
                    _LOGGER.info(
                        "Hisense %s is running. Dynamic cloud polling active: every %d minutes (safe rate)",
                        self.device_type,
                        safe_interval,
                    )
            else:
                if self.update_interval is not None:
                    self.update_interval = None
                    _LOGGER.debug(
                        "Hisense %s is running. Dynamic polling disabled; relying on App countdown timer and MQTT push.",
                        self.device_type,
                    )
        else:
            # 停机/待机/完成：停止本地计时器，并严格关闭轮询（0次云端请求）
            self._stop_app_countdown()
            if self.update_interval is not None:
                self.update_interval = None
                _LOGGER.debug(
                    "Hisense %s is idle/off/complete. Dynamic polling reset to None (zero cloud requests).",
                    self.device_type,
                )

    def _check_washer_completion(self, status: dict[str, Any]) -> None:
        """Trigger completion notification when washer finishes cycle."""
        if self.device_type not in ("洗衣机", "干衣机"):
            return
        is_running = bool(status.get("is_running") or status.get("machine_state") == "running")
        is_complete = (
            status.get("machine_state") == "complete"
            or status.get("run_status") == 7
            or status.get("phase") == 7
        )

        if getattr(self, "_was_running", False) and is_complete:
            self._was_running = False
            dev_name = getattr(self.client, "device_name", self.device_type)
            now_str = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
            self.hass.bus.async_fire(
                "hisense_washer_complete",
                {
                    "device_id": str(self.client.device_id),
                    "device_name": dev_name,
                    "status": "complete",
                    "timestamp": now_str,
                },
            )
            from homeassistant.components import persistent_notification

            persistent_notification.async_create(
                self.hass,
                f"【{dev_name}】洗涤完成！\n时间：{now_str}",
                title=f"海信智慧家 - {self.device_type}完成提醒",
                notification_id=f"hisense_washer_complete_{self.client.device_id}",
            )
        elif is_running:
            self._was_running = True
        elif is_complete:
            pass
        else:
            self._was_running = False

    def async_update_from_client(self) -> None:
        """Push optimistic control state, then read after the cloud settles."""
        self.async_set_updated_data(self.client.get_status())
        self.async_start_refresh(delay=_CONTROL_REFRESH_DELAY)

    async def async_cancel_refresh(self) -> None:
        """Stop delayed retries and countdown timer when the integration unloads."""
        self._stop_app_countdown()
        task = self._refresh_task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._refresh_task = None
