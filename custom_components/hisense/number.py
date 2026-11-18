from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, climate_limits_signal
from .entity import HisenseEntity
from .fridge_const import (
    FREEZE_SET_TEMP_MAX,
    FREEZE_SET_TEMP_MIN,
    REFRIGERATOR_SET_TEMP_MAX,
    REFRIGERATOR_SET_TEMP_MIN,
)

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


FRIDGE_TEMPERATURE_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="refrigerator_temperature",
        translation_key="fridge_refrigerator_target_temperature",
        native_min_value=REFRIGERATOR_SET_TEMP_MIN,
        native_max_value=REFRIGERATOR_SET_TEMP_MAX,
        native_step=1,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:fridge-top",
    ),
    NumberEntityDescription(
        key="freezer_temperature",
        translation_key="fridge_freezer_target_temperature",
        native_min_value=FREEZE_SET_TEMP_MIN,
        native_max_value=FREEZE_SET_TEMP_MAX,
        native_step=1,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:snowflake-thermometer",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    ac_coordinators = [
        c for c in coordinators.values() if c.device_type == "空调"
    ]
    entities = [
        HisenseClimateLimitNumber(coordinator, desc, desc.key == "climate_min_temp")
        for coordinator in ac_coordinators
        for desc in CLIMATE_LIMIT_DESCRIPTIONS
    ]
    async_add_entities(entities)

    fridge_coordinators = [
        c for c in coordinators.values() if c.device_type == "冰箱"
    ]
    async_add_entities(
        HisenseFridgeTemperatureNumber(coordinator, description)
        for coordinator in fridge_coordinators
        for description in FRIDGE_TEMPERATURE_DESCRIPTIONS
    )

    oven_coordinators = [c for c in coordinators.values() if c.device_type == "烤箱"]
    oven_entities = []
    for c in oven_coordinators:
        oven_entities.extend([
            HisenseOvenTargetTemperatureNumber(c),
            HisenseOvenCookTimeNumber(c),
        ])
    if oven_entities:
        async_add_entities(oven_entities)

    water_heater_coordinators = [c for c in coordinators.values() if c.device_type == "热水器"]
    if water_heater_coordinators:
        async_add_entities([HisenseWaterHeaterTargetTemperatureNumber(c) for c in water_heater_coordinators])

    dehumidifier_coordinators = [c for c in coordinators.values() if c.device_type == "除湿机"]
    if dehumidifier_coordinators:
        async_add_entities([HisenseDehumidifierTargetHumidityNumber(c) for c in dehumidifier_coordinators])

    wine_coordinators = [c for c in coordinators.values() if c.device_type == "酒柜"]
    wine_entities = []
    for c in wine_coordinators:
        wine_entities.extend([
            HisenseWineCabinetZone1TemperatureNumber(c),
            HisenseWineCabinetZone2TemperatureNumber(c),
        ])
    if wine_entities:
        async_add_entities(wine_entities)


class HisenseFridgeTemperatureNumber(HisenseEntity, NumberEntity):
    """Writable refrigerator / freezer target temperature."""

    entity_description: NumberEntityDescription

    def __init__(self, coordinator, description: NumberEntityDescription):
        super().__init__(
            coordinator, description.key, description.key, description.icon
        )
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        value = self.status.get(self.entity_description.key)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        target = int(round(value))
        if self.entity_description.key == "refrigerator_temperature":
            ok = await self.client.set_refrigerator_temperature(target)
            action = "冷藏"
        else:
            ok = await self.client.set_freeze_temperature(target)
            action = "冷冻"
        if ok:
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set Hisense fridge {action} temperature")


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


class HisenseOvenTargetTemperatureNumber(HisenseEntity, NumberEntity):
    _attr_translation_key = "oven_target_temperature"
    _attr_native_min_value = 30
    _attr_native_max_value = 250
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, coordinator):
        super().__init__(coordinator, "oven_target_temperature", "oven_target_temperature", "mdi:thermometer-chevron-up")

    @property
    def native_value(self) -> float | None:
        val = self.status.get("target_temperature")
        if val is None:
            return None
        try:
            f_val = float(val)
            if f_val < self._attr_native_min_value:
                return None
            return f_val
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        target = int(round(value))
        if await self.client.set_temperature(target):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense oven target temperature")


class HisenseOvenCookTimeNumber(HisenseEntity, NumberEntity):
    _attr_translation_key = "oven_cook_time"
    _attr_native_min_value = 1
    _attr_native_max_value = 180
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator, "oven_cook_time", "oven_cook_time", "mdi:timer-outline")

    @property
    def native_value(self) -> float | None:
        val = self.status.get("cook_time")
        if val is None:
            return None
        try:
            f_val = float(val)
            if f_val < self._attr_native_min_value:
                return None
            return f_val
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        target = int(round(value))
        if await self.client.set_cook_time(target):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense oven cook time")


class HisenseWaterHeaterTargetTemperatureNumber(HisenseEntity, NumberEntity):
    _attr_translation_key = "water_heater_target_temperature"
    _attr_native_min_value = 35
    _attr_native_max_value = 75
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, coordinator):
        super().__init__(coordinator, "water_heater_target_temperature", "water_heater_target_temperature", "mdi:thermometer-chevron-up")

    @property
    def native_value(self) -> float | None:
        val = self.status.get("target_temperature")
        if val is None:
            return None
        try:
            f_val = float(val)
            if f_val < self._attr_native_min_value:
                return None
            return f_val
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        target = int(round(value))
        if await self.client.set_temperature(target):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense water heater target temperature")


class HisenseDehumidifierTargetHumidityNumber(HisenseEntity, NumberEntity):
    _attr_translation_key = "dehumidifier_target_humidity"
    _attr_native_min_value = 30
    _attr_native_max_value = 80
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:water-percent"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dehumidifier_target_humidity", "dehumidifier_target_humidity", "mdi:water-percent")

    @property
    def native_value(self) -> float | None:
        val = self.status.get("target_humidity")
        if val is None:
            return None
        try:
            f_val = float(val)
            if f_val < self._attr_native_min_value:
                return None
            return f_val
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        target = int(round(value))
        if await self.client.set_target_humidity(target):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense dehumidifier target humidity")


class HisenseWineCabinetZone1TemperatureNumber(HisenseEntity, NumberEntity):
    _attr_translation_key = "wine_cabinet_zone1_target_temperature"
    _attr_native_min_value = 5
    _attr_native_max_value = 20
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, coordinator):
        super().__init__(coordinator, "wine_cabinet_zone1_target_temperature", "wine_cabinet_zone1_target_temperature", "mdi:thermometer-chevron-up")

    @property
    def native_value(self) -> float | None:
        val = self.status.get("zone1_target_temperature")
        if val is None:
            return None
        try:
            f_val = float(val)
            if f_val < self._attr_native_min_value:
                return None
            return f_val
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        target = int(round(value))
        if await self.client.set_zone1_temperature(target):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense wine cabinet zone 1 temperature")


class HisenseWineCabinetZone2TemperatureNumber(HisenseEntity, NumberEntity):
    _attr_translation_key = "wine_cabinet_zone2_target_temperature"
    _attr_native_min_value = 5
    _attr_native_max_value = 20
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, coordinator):
        super().__init__(coordinator, "wine_cabinet_zone2_target_temperature", "wine_cabinet_zone2_target_temperature", "mdi:thermometer-chevron-up")

    @property
    def native_value(self) -> float | None:
        val = self.status.get("zone2_target_temperature")
        if val is None:
            return None
        try:
            f_val = float(val)
            if f_val < self._attr_native_min_value:
                return None
            return f_val
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        target = int(round(value))
        if await self.client.set_zone2_temperature(target):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to set Hisense wine cabinet zone 2 temperature")
