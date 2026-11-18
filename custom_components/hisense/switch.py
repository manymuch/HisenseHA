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
    ac_classes = (
        AcScreenSwitch,
        AuxHeatSwitch,
        FastCoolHeatSwitch,
        NatureWindSwitch,
        PromptSoundSwitch,
        HisenseACVerticalSwingSwitch,
        HisenseACHorizontalSwingSwitch,
        HisenseACAIEcoSwitch,
        HisenseACClearSwitch,
        HisenseACPrevDirectBlowSwitch,
    )
    for cls in ac_classes:
        async_add_entities([cls(coordinator) for coordinator in ac_coordinators])

    fridge_coordinators = [
        c for c in coordinators.values() if c.device_type == "冰箱"
    ]
    for coordinator in fridge_coordinators:
        _add_fridge_degerming_switch(coordinator, async_add_entities)
        for mode, key in (
            ("AI_ECO", "fridge_ai_eco"),
            ("AI_CONTROL_TEMP", "fridge_ai_control_temp"),
            ("QUIET", "fridge_quiet_mode"),
            ("KEEP_FRESH", "fridge_keep_fresh"),
            ("PARTY", "fridge_party"),
            ("POWER_SAVING", "fridge_power_saving"),
            ("QUICK_FROZEN", "fridge_quick_frozen"),
            ("QUICK_DEEP_FROZEN", "fridge_quick_deep_frozen"),
            ("ION_FRESH", "fridge_ion_fresh"),
            ("VARIATION_POWER", "fridge_variation_power"),
        ):
            _add_fridge_ai_switch(coordinator, async_add_entities, mode, key, config_entry)

    dryer_coordinators = [
        c for c in coordinators.values() if c.device_type == "干衣机"
    ]
    dryer_entities = []
    for coordinator in dryer_coordinators:
        dryer_entities.extend([
            HisenseDryerPowerSwitch(coordinator),
            HisenseDryerStartPauseSwitch(coordinator),
            HisenseDryerChildLockSwitch(coordinator),
        ])
    if dryer_entities:
        async_add_entities(dryer_entities)

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

    oven_coordinators = [c for c in coordinators.values() if c.device_type == "烤箱"]
    oven_entities = []
    for coordinator in oven_coordinators:
        oven_entities.extend([
            HisenseOvenPowerSwitch(coordinator),
            HisenseOvenStartPauseSwitch(coordinator),
            HisenseOvenChildLockSwitch(coordinator),
        ])
    if oven_entities:
        async_add_entities(oven_entities)

    dishwasher_coordinators = [c for c in coordinators.values() if c.device_type == "洗碗机"]
    dishwasher_entities = []
    for coordinator in dishwasher_coordinators:
        dishwasher_entities.extend([
            HisenseDishwasherPowerSwitch(coordinator),
            HisenseDishwasherStartPauseSwitch(coordinator),
            HisenseDishwasherChildLockSwitch(coordinator),
        ])
    if dishwasher_entities:
        async_add_entities(dishwasher_entities)

    water_heater_coordinators = [c for c in coordinators.values() if c.device_type == "热水器"]
    if water_heater_coordinators:
        async_add_entities([HisenseWaterHeaterPowerSwitch(c) for c in water_heater_coordinators])

    hood_coordinators = [c for c in coordinators.values() if c.device_type == "油烟机"]
    hood_entities = []
    for coordinator in hood_coordinators:
        hood_entities.extend([
            HisenseHoodPowerSwitch(coordinator),
            HisenseHoodLightSwitch(coordinator),
            HisenseHoodDelayOffSwitch(coordinator),
        ])
    if hood_entities:
        async_add_entities(hood_entities)

    dehumidifier_coordinators = [c for c in coordinators.values() if c.device_type == "除湿机"]
    dehumidifier_entities = []
    for coordinator in dehumidifier_coordinators:
        dehumidifier_entities.extend([
            HisenseDehumidifierPowerSwitch(coordinator),
            HisenseDehumidifierChildLockSwitch(coordinator),
        ])
    if dehumidifier_entities:
        async_add_entities(dehumidifier_entities)

    fresh_air_coordinators = [c for c in coordinators.values() if c.device_type == "新风系统"]
    if fresh_air_coordinators:
        async_add_entities([HisenseFreshAirPowerSwitch(c) for c in fresh_air_coordinators])

    wine_coordinators = [c for c in coordinators.values() if c.device_type == "酒柜"]
    wine_entities = []
    for coordinator in wine_coordinators:
        wine_entities.extend([
            HisenseWineCabinetPowerSwitch(coordinator),
            HisenseWineCabinetLightSwitch(coordinator),
        ])
    if wine_entities:
        async_add_entities(wine_entities)



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


class HisenseACVerticalSwingSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "ac_vertical_swing"
    _attr_icon = "mdi:arrow-up-down"

    def __init__(self, coordinator):
        super().__init__(coordinator, "ac_vertical_swing", "ac_vertical_swing")

    @property
    def is_on(self):
        return self.status.get("up_down_wind_full_control")

    async def async_turn_on(self):
        if await self.client.set_vertical_swing(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC vertical swing")

    async def async_turn_off(self):
        if await self.client.set_vertical_swing(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC vertical swing")


class HisenseACHorizontalSwingSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "ac_horizontal_swing"
    _attr_icon = "mdi:arrow-left-right"

    def __init__(self, coordinator):
        super().__init__(coordinator, "ac_horizontal_swing", "ac_horizontal_swing")

    @property
    def is_on(self):
        return self.status.get("left_right_wind_full_control")

    async def async_turn_on(self):
        if await self.client.set_horizontal_swing(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC horizontal swing")

    async def async_turn_off(self):
        if await self.client.set_horizontal_swing(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC horizontal swing")


class HisenseACAIEcoSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "ac_ai_eco"
    _attr_icon = "mdi:leaf"

    def __init__(self, coordinator):
        super().__init__(coordinator, "ac_ai_eco", "ac_ai_eco")

    @property
    def is_on(self):
        return self.status.get("ai_eco_mode")

    async def async_turn_on(self):
        if await self.client.set_ai_eco_mode(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC AI Eco mode")

    async def async_turn_off(self):
        if await self.client.set_ai_eco_mode(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC AI Eco mode")


class HisenseACClearSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "ac_clear"
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator):
        super().__init__(coordinator, "ac_clear", "ac_clear")

    @property
    def is_on(self):
        return self.status.get("clear_switch")

    async def async_turn_on(self):
        if await self.client.set_clear_switch(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC clear")

    async def async_turn_off(self):
        if await self.client.set_clear_switch(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC clear")


class HisenseACPrevDirectBlowSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "ac_prev_direct_blow"
    _attr_icon = "mdi:account-arrow-right"

    def __init__(self, coordinator):
        super().__init__(coordinator, "ac_prev_direct_blow", "ac_prev_direct_blow")

    @property
    def is_on(self):
        return self.status.get("prev_direct_blow")

    async def async_turn_on(self):
        if await self.client.set_prev_direct_blow(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC anti-direct blow")

    async def async_turn_off(self):
        if await self.client.set_prev_direct_blow(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC anti-direct blow")


class HisenseDryerPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "dryer_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dryer_power", "dryer_power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense dryer")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense dryer")


class HisenseDryerStartPauseSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "dryer_start_pause"
    _attr_icon = "mdi:play-pause"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dryer_start_pause", "dryer_start_pause")

    @property
    def is_on(self):
        return self.status.get("is_running")

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot start Hisense dryer while powered off")
        if await self.client.start_pause(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to start Hisense dryer")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot pause Hisense dryer while powered off")
        if await self.client.start_pause(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to pause Hisense dryer")


class HisenseDryerChildLockSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "dryer_child_lock"
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dryer_child_lock", "dryer_child_lock")

    @property
    def is_on(self):
        return self.status.get("child_lock")

    async def async_turn_on(self):
        if await self.client.set_child_lock(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to enable Hisense dryer child lock")

    async def async_turn_off(self):
        if await self.client.set_child_lock(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to disable Hisense dryer child lock")


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
        return bool(self.status.get("is_running") or self.status.get("machine_state") == "running")

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
        if not (self.status.get("is_running") or self.status.get("machine_state") == "running" or self.status.get("run_state")):
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
        if not (self.status.get("is_running") or self.status.get("machine_state") == "running" or self.status.get("run_state")):
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


# ============================================================================
# 新增家电设备开关类：蒸烤箱、洗碗机、热水器、油烟机、除湿机、新风系统、酒柜
# ============================================================================

class HisenseOvenPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "oven_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "oven_power", "oven_power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense oven")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense oven")


class HisenseOvenStartPauseSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "oven_start_pause"
    _attr_icon = "mdi:play-pause"

    def __init__(self, coordinator):
        super().__init__(coordinator, "oven_start_pause", "oven_start_pause")

    @property
    def is_on(self):
        return self.status.get("is_running")

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot start Hisense oven while powered off")
        if await self.client.start_pause(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to start Hisense oven")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot pause Hisense oven while powered off")
        if await self.client.start_pause(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to pause Hisense oven")


class HisenseOvenChildLockSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "oven_child_lock"
    _attr_icon = "mdi:account-lock"

    def __init__(self, coordinator):
        super().__init__(coordinator, "oven_child_lock", "oven_child_lock")

    @property
    def is_on(self):
        return self.status.get("child_lock")

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot set child lock while oven is powered off")
        if await self.client.set_child_lock(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to enable child lock for Hisense oven")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot set child lock while oven is powered off")
        if await self.client.set_child_lock(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to disable child lock for Hisense oven")


class HisenseDishwasherPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "dishwasher_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dishwasher_power", "dishwasher_power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense dishwasher")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense dishwasher")


class HisenseDishwasherStartPauseSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "dishwasher_start_pause"
    _attr_icon = "mdi:play-pause"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dishwasher_start_pause", "dishwasher_start_pause")

    @property
    def is_on(self):
        return self.status.get("is_running")

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot start Hisense dishwasher while powered off")
        if await self.client.start_pause(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to start Hisense dishwasher")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot pause Hisense dishwasher while powered off")
        if await self.client.start_pause(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to pause Hisense dishwasher")


class HisenseDishwasherChildLockSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "dishwasher_child_lock"
    _attr_icon = "mdi:account-lock"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dishwasher_child_lock", "dishwasher_child_lock")

    @property
    def is_on(self):
        return self.status.get("child_lock")

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot set child lock while dishwasher is powered off")
        if await self.client.set_child_lock(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to enable child lock for Hisense dishwasher")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot set child lock while dishwasher is powered off")
        if await self.client.set_child_lock(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to disable child lock for Hisense dishwasher")


class HisenseWaterHeaterPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "water_heater_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "water_heater_power", "water_heater_power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense water heater")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense water heater")


class HisenseHoodPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "hood_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "hood_power", "hood_power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense hood")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense hood")


class HisenseHoodLightSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "hood_light"
    _attr_icon = "mdi:lightbulb"

    def __init__(self, coordinator):
        super().__init__(coordinator, "hood_light", "hood_light")

    @property
    def is_on(self):
        return self.status.get("light_on")

    async def async_turn_on(self):
        if await self.client.set_light(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense hood light")

    async def async_turn_off(self):
        if await self.client.set_light(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense hood light")


class HisenseHoodDelayOffSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "hood_delay_off"
    _attr_icon = "mdi:clock-end"

    def __init__(self, coordinator):
        super().__init__(coordinator, "hood_delay_off", "hood_delay_off")

    @property
    def is_on(self):
        return self.status.get("delay_off")

    async def async_turn_on(self):
        if await self.client.set_delay_off(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to enable delay off for Hisense hood")

    async def async_turn_off(self):
        if await self.client.set_delay_off(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to disable delay off for Hisense hood")


class HisenseDehumidifierPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "dehumidifier_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dehumidifier_power", "dehumidifier_power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense dehumidifier")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense dehumidifier")


class HisenseDehumidifierChildLockSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "dehumidifier_child_lock"
    _attr_icon = "mdi:account-lock"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dehumidifier_child_lock", "dehumidifier_child_lock")

    @property
    def is_on(self):
        return self.status.get("child_lock")

    async def async_turn_on(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot set child lock while dehumidifier is powered off")
        if await self.client.set_child_lock(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to enable child lock for Hisense dehumidifier")

    async def async_turn_off(self):
        if not self.status.get("power_on"):
            raise HomeAssistantError("Cannot set child lock while dehumidifier is powered off")
        if await self.client.set_child_lock(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to disable child lock for Hisense dehumidifier")


class HisenseFreshAirPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "fresh_air_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "fresh_air_power", "fresh_air_power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense fresh air system")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense fresh air system")


class HisenseWineCabinetPowerSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "wine_cabinet_power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator, "wine_cabinet_power", "wine_cabinet_power")

    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense wine cabinet")

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense wine cabinet")


class HisenseWineCabinetLightSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "wine_cabinet_light"
    _attr_icon = "mdi:lightbulb"

    def __init__(self, coordinator):
        super().__init__(coordinator, "wine_cabinet_light", "wine_cabinet_light")

    @property
    def is_on(self):
        return self.status.get("light_on")

    async def async_turn_on(self):
        if await self.client.set_light(True):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense wine cabinet light")

    async def async_turn_off(self):
        if await self.client.set_light(False):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense wine cabinet light")
