import asyncio

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, climate_limits_signal
from .entity import HisenseEntity

CLIMATE_LIMIT_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="climate_min_temp",
        translation_key="climate_min_temp",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    NumberEntityDescription(
        key="climate_max_temp",
        translation_key="climate_max_temp",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)


FRIDGE_TEMP_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="refrigerator_temp_control",
        translation_key="refrigerator_temp_control",
        native_min_value=2,
        native_max_value=8,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    NumberEntityDescription(
        key="freeze_temp_control",
        translation_key="freeze_temp_control",
        native_min_value=-25,
        native_max_value=-15,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:snowflake-thermometer",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    ac_coordinators = [
        c for c in coordinators.values() if c.device_type == "空调"
    ]
    fridge_coordinators = [
        c for c in coordinators.values() if c.device_type == "冰箱"
    ]

    entities = [
        HisenseClimateLimitNumber(coordinator, desc, desc.key == "climate_min_temp")
        for coordinator in ac_coordinators
        for desc in CLIMATE_LIMIT_DESCRIPTIONS
    ]

    fridge_entities = [
        HisenseFridgeTemperatureNumber(coordinator, desc)
        for coordinator in fridge_coordinators
        for desc in FRIDGE_TEMP_DESCRIPTIONS
    ]

    async_add_entities(entities + fridge_entities)


class HisenseClimateLimitNumber(HisenseEntity, NumberEntity):
    """Configuration slider for climate min or max temperature bound (0–100 °C)."""

    entity_description: NumberEntityDescription

    def __init__(self, coordinator, description: NumberEntityDescription, is_min: bool):
        super().__init__(coordinator, description.key, description.key)
        self.entity_description = description
        self._is_min = is_min

    @property
    def native_value(self) -> float | None:
        if self._is_min:
            return float(self.client.climate_min_temp)
        return float(self.client.climate_max_temp)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                climate_limits_signal(self.client.device_id),
                self._handle_limits_updated,
            )
        )

    @callback
    def _handle_limits_updated(self, *_args):
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        v = int(max(0, min(100, round(value))))
        if self._is_min:
            self.client.climate_min_temp = v
            if self.client.climate_min_temp > self.client.climate_max_temp:
                self.client.climate_max_temp = self.client.climate_min_temp
        else:
            self.client.climate_max_temp = v
            if self.client.climate_max_temp < self.client.climate_min_temp:
                self.client.climate_min_temp = self.client.climate_max_temp
        async_dispatcher_send(self.hass, climate_limits_signal(self.client.device_id))
        self.async_write_ha_state()


class HisenseFridgeTemperatureNumber(HisenseEntity, NumberEntity):
    entity_description: NumberEntityDescription

    def __init__(self, coordinator, description: NumberEntityDescription):
        super().__init__(coordinator, description.key, description.key, description.icon)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        work_mode = self.status.get("work_mode", "自定义")
        
        if self.entity_description.key == "refrigerator_temp_control":
            if work_mode == "智能":
                return 5.0
            if work_mode == "速冷":
                return 2.0
            return float(self.status.get("refrigerator_set_temperature", 5))
        
        if work_mode == "智能":
            return -18.0
        if work_mode == "速冷":
            return -16.0
        return float(self.status.get("freeze_set_temperature", -18))

    async def async_set_native_value(self, value: float) -> None:
        v = round(value)
        
        if self.entity_description.key == "refrigerator_temp_control":
            success = await self.client.set_refrigerator_temperature(v)
            label = "refrigerator"
            data_key = "refrigerator_set_temperature"
        else:
            success = await self.client.set_freeze_temperature(v)
            label = "freezer"
            data_key = "freeze_set_temperature"
        if not success:
            raise HomeAssistantError(f"Failed to set Hisense {label} temperature")

        self.coordinator.data[data_key] = v
        
        work_mode = self.status.get("work_mode", "自定义")
        if work_mode == "智能" or work_mode == "速冷":
            self.coordinator.data["work_mode"] = "自定义"
            self.coordinator.data["work_mode_id"] = 0
            
            if self.entity_description.key == "refrigerator_temp_control":
                if work_mode == "智能":
                    self.coordinator.data["freeze_set_temperature"] = -18
                else:
                    self.coordinator.data["freeze_set_temperature"] = -16
            else:
                if work_mode == "智能":
                    self.coordinator.data["refrigerator_set_temperature"] = 5
                else:
                    self.coordinator.data["refrigerator_set_temperature"] = 2
        
        self.coordinator.async_set_updated_data(self.coordinator.data)
        
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
