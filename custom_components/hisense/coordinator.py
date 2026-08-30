"""Data update coordinator for Hisense devices."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .pyhisenseapi import HiSenseAC, HiSenseFridge, HiSenseWasher

import logging

_LOGGER = logging.getLogger(__name__)
_CONTROL_REFRESH_DELAY = 1.0


class HisenseDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for a single Hisense device (AC or Fridge)."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: HiSenseAC | HiSenseFridge | HiSenseWasher,
        device_type: str = "空调"
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_type = device_type
        self._control_refresh_task: asyncio.Task | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.device_id}",
            update_interval=None,
        )

    async def _async_setup(self) -> None:
        """Validate the stored AIHome credentials before the first fetch."""
        try:
            refreshed = await self.client.refresh()
        except Exception as err:
            raise UpdateFailed("Failed to validate Hisense AIHome credentials") from err
        if refreshed:
            return
        raise UpdateFailed("Failed to validate Hisense AIHome credentials")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh state from the Hisense cloud."""
        try:
            status = await self.client.check_status()
            if status and self.device_type == "空调" and hasattr(self.client, "get_energy"):
                energy_status = await self.client.get_energy()
                if energy_status:
                    status = energy_status
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch Hisense {self.device_type} status") from err
        if not status:
            raise UpdateFailed(f"Failed to fetch Hisense {self.device_type} status")
        return status

    def async_update_from_client(self) -> None:
        """Push optimistic state, then refresh after the cloud settles."""
        self.async_set_updated_data(self.client.get_status())
        if self._control_refresh_task and not self._control_refresh_task.done():
            self._control_refresh_task.cancel()
        self._control_refresh_task = self.hass.async_create_task(
            self._async_refresh_after_control()
        )

    async def _async_refresh_after_control(self) -> None:
        """Avoid overwriting an accepted control with a stale detail response."""
        try:
            await asyncio.sleep(_CONTROL_REFRESH_DELAY)
            await self.async_request_refresh()
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.debug("Delayed Hisense control refresh failed", exc_info=True)
        finally:
            if self._control_refresh_task is asyncio.current_task():
                self._control_refresh_task = None
