from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity

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
