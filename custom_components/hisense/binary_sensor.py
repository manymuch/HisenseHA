from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .entity import HisenseEntity

WASHER_BINARY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="power_on", translation_key="washer_power", icon="mdi:power"
    ),
    BinarySensorEntityDescription(
        key="gate_locked", translation_key="washer_gate_lock", icon="mdi:lock"
    ),
    BinarySensorEntityDescription(
        key="child_lock",
        translation_key="washer_child_lock",
        icon="mdi:account-lock",
    ),
)

DRYER_BINARY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="power_on", translation_key="dryer_power", icon="mdi:power"
    ),
    BinarySensorEntityDescription(
        key="gate_locked", translation_key="dryer_gate_lock", icon="mdi:lock"
    ),
    BinarySensorEntityDescription(
        key="child_lock",
        translation_key="dryer_child_lock",
        icon="mdi:account-lock",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    washer_coordinators = [
        coordinator
        for coordinator in coordinators.values()
        if coordinator.device_type == "洗衣机"
    ]
    async_add_entities(
        HisenseWasherBinarySensor(coordinator, description)
        for coordinator in washer_coordinators
        for description in WASHER_BINARY_SENSOR_DESCRIPTIONS
    )

    dryer_coordinators = [
        coordinator
        for coordinator in coordinators.values()
        if coordinator.device_type == "干衣机"
    ]
    async_add_entities(
        HisenseDryerBinarySensor(coordinator, description)
        for coordinator in dryer_coordinators
        for description in DRYER_BINARY_SENSOR_DESCRIPTIONS
    )


class HisenseWasherBinarySensor(HisenseEntity, BinarySensorEntity):
    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, description):
        super().__init__(coordinator, description.key, description.key, description.icon)
        self.entity_description = description

    @property
    def is_on(self):
        return self.status.get(self.entity_description.key)


class HisenseDryerBinarySensor(HisenseEntity, BinarySensorEntity):
    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, description):
        super().__init__(coordinator, description.key, description.key, description.icon)
        self.entity_description = description

    @property
    def is_on(self):
        return self.status.get(self.entity_description.key)
