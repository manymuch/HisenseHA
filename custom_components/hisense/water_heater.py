from homeassistant.components.water_heater import (
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity
from .pyhisenseapi import HiSenseWaterHeater

MODES = {1: "即时加热", 2: "中温节能", 3: "水质巡航", 4: "大水量"}
MODE_TO_ID = {name: mode_id for mode_id, name in MODES.items()}


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        HisenseWaterHeaterEntity(coordinator)
        for coordinator in coordinators.values()
        if coordinator.device_type == "热水器"
    )


class HisenseWaterHeaterEntity(HisenseEntity, WaterHeaterEntity):
    _attr_name = "Water Heater"
    _attr_min_temp = HiSenseWaterHeater.MIN_TEMPERATURE
    _attr_max_temp = HiSenseWaterHeater.MAX_TEMPERATURE
    _attr_target_temperature_step = 1
    _attr_operation_list = [STATE_OFF, *MODES.values()]
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )

    if hasattr(WaterHeaterEntity, "native_temperature_unit"):
        _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    else:
        _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator):
        super().__init__(coordinator, "water_heater", "water_heater")

    @property
    def native_current_temperature(self):
        return self.status.get("current_temperature")

    @property
    def native_target_temperature(self):
        return self.status.get("target_temperature")

    if not hasattr(WaterHeaterEntity, "native_temperature_unit"):
        current_temperature = native_current_temperature
        target_temperature = native_target_temperature

    @property
    def current_operation(self):
        power_on = self.status.get("power_on")
        if power_on is False:
            return STATE_OFF
        return MODES.get(self.status.get("work_mode")) if power_on else None

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if not await self.client.set_temperature(temperature):
            raise HomeAssistantError("Failed to set Hisense water heater temperature")
        self.coordinator.async_update_from_client()

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
            return
        mode_id = MODE_TO_ID.get(operation_mode)
        if mode_id is None or not await self.client.set_mode(mode_id):
            raise HomeAssistantError("Failed to set Hisense water heater mode")
        self.coordinator.async_update_from_client()

    async def async_turn_on(self, **kwargs):
        if not await self.client.turn_on():
            raise HomeAssistantError("Failed to turn on Hisense water heater")
        self.coordinator.async_update_from_client()

    async def async_turn_off(self, **kwargs):
        if not await self.client.turn_off():
            raise HomeAssistantError("Failed to turn off Hisense water heater")
        self.coordinator.async_update_from_client()
