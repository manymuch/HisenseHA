from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity
from .fridge_const import WORK_MODE_STATUS_KEYS
from .pyhisenseapi import WASHER_PROGRAM_REVERSE_MAP

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    ac_coordinators = [
        c for c in coordinators.values() if c.device_type == "空调"
    ]
    entities = [AcScreenSwitch(coordinator) for coordinator in ac_coordinators]
    async_add_entities(entities)
    entities = [AuxHeatSwitch(coordinator) for coordinator in ac_coordinators]
    async_add_entities(entities)
    entities = [FastCoolHeatSwitch(coordinator) for coordinator in ac_coordinators]
    async_add_entities(entities)
    entities = [NatureWindSwitch(coordinator) for coordinator in ac_coordinators]
    async_add_entities(entities)
    entities = [PromptSoundSwitch(coordinator) for coordinator in ac_coordinators]
    async_add_entities(entities)

    fridge_coordinators = [
        c for c in coordinators.values() if c.device_type == "冰箱"
    ]
    for coordinator in fridge_coordinators:
        _add_fridge_degerming_switch(coordinator, async_add_entities)
        for mode, key in (
            ("AI_ECO", "fridge_ai_eco"),
            ("AI_CONTROL_TEMP", "fridge_ai_control_temp"),
            ("QUIET", "fridge_quiet_mode"),
        ):
            _add_fridge_ai_switch(coordinator, async_add_entities, mode, key, config_entry)

    washer_coordinators = [
        c for c in coordinators.values() if c.device_type == "洗衣机"
    ]
    washer_entities = []
    for coordinator in washer_coordinators:
        washer_entities.extend([
            HisenseWasherPowerSwitch(coordinator),
            HisenseWasherStartPauseSwitch(coordinator),
            HisenseWasherChildLockSwitch(coordinator),
            HisenseWasherSoftbakingSwitch(coordinator),
        ])
    if washer_entities:
        async_add_entities(washer_entities)



def _add_fridge_degerming_switch(coordinator, async_add_entities):
    """Create the degerming switch only for models that report the flag.

    ``dBDDegerming`` is ``None`` both for "not supported" and for "states not
    read yet", so we need the alarm-support map (only produced by a full
    parse) to tell them apart: without it we must wait, otherwise a fridge that
    happens to be offline during HA startup would lose the switch until reload.
    """
    if coordinator.__dict__.get("_fridge_degerming_switch_added"):
        return
    status = coordinator.data or coordinator.client.get_status()
    if status.get("degerming_active") is not None:
        coordinator.__dict__["_fridge_degerming_switch_added"] = True
        async_add_entities([HisenseFridgeDegermingSwitch(coordinator)])
        return
    if status.get("unsupported_alarms") is not None:
        # 完整 states 读到了、但依然没有除菌位 → 本机没有这个功能。
        return

    remove_listener = None

    def _on_update():
        if remove_listener is not None:
            remove_listener()
        _add_fridge_degerming_switch(coordinator, async_add_entities)

    remove_listener = coordinator.async_add_listener(_on_update)


class HisenseFridgeDegermingSwitch(HisenseEntity, SwitchEntity):
    """DBD degerming + odor removal cycle.

    One command (``DBDDegerming``) drives both: starting it turns on the ion
    degerming unit and the odor-removal path together, so the entity is named
    "degerming + odor removal" rather than just "degerming".

    ``dBDDegerming`` reports whether a cycle is currently running, so the switch
    flips itself back to off when the cycle finishes — that is the real state, not
    a UI artefact. Read-only monitoring is available separately as
    ``binary_sensor.fridge_degerming_active``, because a cycle may also be
    started by the appliance itself (schedule), not only from here.
    """

    _attr_translation_key = "fridge_degerming"
    _attr_icon = "mdi:shield-sun"

    def __init__(self, coordinator):
        super().__init__(coordinator, "fridge_degerming", "fridge_degerming")

    @property
    def is_on(self):
        return self.status.get("degerming_active")

    @property
    def extra_state_attributes(self):
        bits = self.status.get("degerming_bits") or {}
        return {f"raw_{key}": value for key, value in bits.items()}

    async def async_turn_on(self):
        if await self.client.set_fridge_degerming(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to start Hisense fridge degerming")

    async def async_turn_off(self):
        if await self.client.set_fridge_degerming(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to stop Hisense fridge degerming")


def _add_fridge_ai_switch(
    coordinator, async_add_entities, mode: str, key: str, config_entry
):
    """Create an independent fridge switch only when the model reports the bit.

    Used for AI节能 / AI恒温 / 智能降噪.
    """
    sentinel = f"_fridge_{key}_added"
    if coordinator.__dict__.get(sentinel):
        return
    status_key = WORK_MODE_STATUS_KEYS[mode]
    remove_listener = None

    def _on_update():
        status = coordinator.data or coordinator.client.get_status()
        if status.get(status_key) is None:
            return
        if remove_listener is not None:
            remove_listener()
        coordinator.__dict__[sentinel] = True
        async_add_entities([HisenseFridgeModeSwitch(coordinator, mode, key)])

    _on_update()
    if not coordinator.__dict__.get(sentinel):
        remove_listener = coordinator.async_add_listener(_on_update)
        config_entry.async_on_unload(remove_listener)


class HisenseFridgeModeSwitch(HisenseEntity, SwitchEntity):
    """冰箱独立开关：AI节能 / AI恒温 / 智能降噪。

    这些是独立功能位，可以与工作模式（日常/速冷/急冻/假日）并存，
    因此做成 switch 而不是 select 选项。
    """

    def __init__(self, coordinator, mode: str, key: str):
        super().__init__(coordinator, key, key)
        self._mode = mode
        self._status_key = WORK_MODE_STATUS_KEYS[mode]
        self._attr_translation_key = key
        self._attr_icon = {
            "AI_ECO": "mdi:leaf",
            "AI_CONTROL_TEMP": "mdi:thermometer-auto",
            "QUIET": "mdi:volume-off",
        }.get(mode, "mdi:toggle-switch")

    @property
    def available(self):
        return super().available and self.status.get(self._status_key) is not None

    @property
    def is_on(self):
        return self.status.get(self._status_key)

    async def async_turn_on(self):
        if await self.client.set_fridge_mode(self._mode, enable=True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to turn on Hisense fridge {self._mode}")

    async def async_turn_off(self):
        if await self.client.set_fridge_mode(self._mode, enable=False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to turn off Hisense fridge {self._mode}")


class AcScreenSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "screen_panel"

    def __init__(self, coordinator):
        super().__init__(coordinator, "screen", "screen")
        self._attr_icon = "mdi:clock-digital"

    @property
    def is_on(self):
        return self.status.get("screen_on")

    async def async_turn_on(self):
        _LOGGER.debug(f"Turning on screen for {self._attr_unique_id}")
        if await self.client.set_screen_switch(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC screen")

    async def async_turn_off(self):
        _LOGGER.debug(f"Turning off screen for {self._attr_unique_id}")
        if await self.client.set_screen_switch(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC screen")


class AuxHeatSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "auxiliary_heat"

    def __init__(self, coordinator):
        super().__init__(coordinator, "aux_heat", "aux_heat")
        self._attr_icon = "mdi:heating-coil"

    @property
    def is_on(self):
        return self.status.get("aux_heat")

    async def async_turn_on(self):
        if await self.client.set_heat_switch(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC auxiliary heat")

    async def async_turn_off(self):
        if await self.client.set_heat_switch(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC auxiliary heat")


class FastCoolHeatSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "fast_cool_heat"

    def __init__(self, coordinator):
        super().__init__(coordinator, "fast_cool_heat", "fast_cool_heat")
        self._attr_icon = "mdi:fan-plus"

    @property
    def is_on(self):
        return self.status.get("fast_cool_heat")

    async def async_turn_on(self):
        if await self.client.set_fast_cool_heat(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC fast cool/heat")

    async def async_turn_off(self):
        if await self.client.set_fast_cool_heat(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC fast cool/heat")


class NatureWindSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "nature_wind"

    def __init__(self, coordinator):
        super().__init__(coordinator, "nature_wind", "nature_wind")
        self._attr_icon = "mdi:weather-windy"

    @property
    def is_on(self):
        return self.status.get("nature_wind")

    async def async_turn_on(self):
        if await self.client.set_nature_wind(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC nature wind")

    async def async_turn_off(self):
        if await self.client.set_nature_wind(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC nature wind")


class PromptSoundSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "prompt_sound"

    def __init__(self, coordinator):
        super().__init__(coordinator, "prompt_sound", "prompt_sound")
        self._attr_icon = "mdi:volume-high"

    @property
    def is_on(self):
        return self.status.get("prompt_sound")

    async def async_turn_on(self):
        if await self.client.set_prompt_sound(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC prompt sound")

    async def async_turn_off(self):
        if await self.client.set_prompt_sound(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC prompt sound")


class HisenseWasherPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "washer_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_power", "washer_power", "mdi:power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.set_power(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("海信洗衣机硬件安全策略限制：关机状态下不支持远程通电开机，请在物理面板按电源键开机")

    async def async_turn_off(self):
        if await self.client.set_power(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("远程关机失败")


class HisenseWasherStartPauseSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "washer_start_pause"
    _attr_icon = "mdi:play-pause"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_start_pause", "washer_start_pause", "mdi:play-pause")

    @property
    def is_on(self):
        return self.status.get("run_state") == 1

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源")
        if await self.client.set_start_stop(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("启动洗衣机失败（请检查机门是否关严或面板是否开启远程控制）")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机")
        if await self.client.set_start_stop(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("暂停洗衣机失败")


class HisenseWasherChildLockSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "washer_child_lock"
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_child_lock", "washer_child_lock", "mdi:lock")

    @property
    def is_on(self):
        return self.status.get("child_lock")

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，无法设置童锁（需开机运转中设置）")
        if not self.status.get("run_state"):
            raise HomeAssistantError("海信洗衣机硬件安全规范：未在洗涤运转中不可设置童锁，请在机器启动洗涤后开启或关闭童锁")
        if self.status.get("start_pause_status"):
            raise HomeAssistantError("暂停状态下，童锁不可设")
        if await self.client.set_child_lock(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("设置童锁失败")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，无法设置童锁")
        if not self.status.get("run_state"):
            raise HomeAssistantError("海信洗衣机硬件安全规范：未在洗涤运转中不可设置童锁")
        if self.status.get("start_pause_status"):
            raise HomeAssistantError("暂停状态下，童锁不可设")
        if await self.client.set_child_lock(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("关闭童锁失败")


class HisenseWasherSoftbakingSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "washer_softbaking"
    _attr_icon = "mdi:snowflake-thermometer"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_softbaking", "washer_softbaking", "mdi:snowflake-thermometer")

    @property
    def is_on(self):
        return bool(self.status.get("softbaking") or self.status.get("drying_modes") == 1)

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源")
        cur_program = str(self.status.get("program_code", self.status.get("program", "")))
        if cur_program not in ("35", "Single_dry"):
            prog_name = self.status.get("program_name") or WASHER_PROGRAM_REVERSE_MAP.get(cur_program, "当前程序")
            raise HomeAssistantError(
                f"海信洗衣机硬件固件限制：【低温烘】属于【单烘】程序的专属烘干模式（与标准烘对应，可搭配即穿/即存或定时烘干共存）。"
                f"当前程序为【{prog_name}】，固件不支持在此程序下开启低温烘。请先在“洗衣程序”中切换为【单烘】，即可开启低温烘！"
            )
        if await self.client.set_softbaking(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("开启低温烘失败")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源")
        if await self.client.set_softbaking(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("关闭低温烘失败")
