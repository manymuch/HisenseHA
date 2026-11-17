from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_OFF,  # <--- 新增引入
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .entity import HisenseEntity

MODES = {1: "即时加热", 2: "中温节能", 3: "水质巡航", 4: "大水量"}
MODE_TO_ID = {"即时加热": 1, "中温节能": 2, "水质巡航": 3, "大水量": 4}

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    wh_coordinators = [c for c in coordinators.values() if c.device_type == "热水器"]
    async_add_entities(
        HisenseWaterHeaterEntity(coordinator) for coordinator in wh_coordinators
    )

class HisenseWaterHeaterEntity(HisenseEntity, WaterHeaterEntity):
    _attr_name = "Water Heater"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 30.0
    _attr_max_temp = 75.0
    _attr_target_temperature_step = 1.0
    _attr_operation_list = list(MODES.values())
    
    def __init__(self, coordinator):
        super().__init__(coordinator, "water_heater", "water_heater")
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
            | WaterHeaterEntityFeature.ON_OFF
        )

    @property
    def current_temperature(self):
        return self.status.get("current_temperature")

    @property
    def target_temperature(self):
        return self.status.get("target_temperature")

    @property
    def current_operation(self):
        # ====== 核心修改：如果关机，必须返回 STATE_OFF ======
        if not self.status.get("power_on"):
            return STATE_OFF
            
        mode = self.status.get("work_mode")
        if mode is None:
            return None
        return MODES.get(mode, "未知")

    # ====== 新增 is_on 属性，告诉前端到底开没开机 ======
    @property
    def is_on(self):
        return self.status.get("power_on")

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            temp = int(kwargs[ATTR_TEMPERATURE])
            if await self.client.set_temperature(temp):
                self.coordinator.async_update_from_client()
            else:
                raise HomeAssistantError("设置水温失败")

    async def async_set_operation_mode(self, operation_mode):
        mode_id = MODE_TO_ID.get(operation_mode)
        if mode_id is not None:
            if await self.client.set_mode(mode_id):
                self.coordinator.async_update_from_client()
            else:
                raise HomeAssistantError(f"设置模式 {operation_mode} 失败")

    async def async_turn_on(self):
        if await self.client.turn_on():
            self.coordinator.async_update_from_client()

    async def async_turn_off(self):
        if await self.client.turn_off():
            self.coordinator.async_update_from_client()