from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .entity import HisenseEntity

FRIDGE_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="refrigerator_set_temperature",
        translation_key="refrigerator_set_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="freeze_set_temperature",
        translation_key="freeze_set_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:snowflake-thermometer",
    ),
    SensorEntityDescription(
        key="refrigerator_real_temperature",
        translation_key="refrigerator_real_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="freeze_real_temperature",
        translation_key="freeze_real_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:snowflake-thermometer",
    ),
    SensorEntityDescription(
        key="variation_real_temperature",
        translation_key="variation_real_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="work_mode",
        translation_key="work_mode",
        icon="mdi:format-list-bulleted",
    ),
    SensorEntityDescription(
        key="variation_mode",
        translation_key="variation_mode",
        icon="mdi:format-list-bulleted",
    ),
    SensorEntityDescription(
        key="ambient_temperature",
        translation_key="ambient_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    fridge_coordinators = [
        c for c in coordinators.values() if c.device_type == "冰箱"
    ]

    sensors = [
        HisenseFridgeSensor(coordinator, desc)
        for coordinator in fridge_coordinators
        for desc in FRIDGE_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(sensors)


class HisenseFridgeSensor(HisenseEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription):
        super().__init__(
            coordinator,
            description.key,
            description.key,
            description.icon,
        )
        self.entity_description = description

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self.status.get(self.entity_description.key)
