from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfTime
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import HisenseEntity

AC_ENERGY_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="today_energy",
        translation_key="today_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="run_time",
        translation_key="run_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:timer-outline",
    ),
)

WASHER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="machine_state",
        translation_key="washer_run_state",
        icon="mdi:washing-machine",
    ),
    SensorEntityDescription(
        key="phase_label",
        translation_key="washer_phase",
        icon="mdi:progress-clock",
    ),
    SensorEntityDescription(
        key="program",
        translation_key="washer_program",
        icon="mdi:format-list-numbered",
    ),
    SensorEntityDescription(
        key="remaining_minutes",
        translation_key="washer_remaining_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="fault",
        translation_key="washer_fault",
        icon="mdi:alert-circle-outline",
    ),
    SensorEntityDescription(
        key="motor_speed",
        translation_key="washer_motor_speed",
        native_unit_of_measurement="rpm",
        icon="mdi:rotate-right",
    ),
    SensorEntityDescription(
        key="temperature_raw",
        translation_key="washer_temperature_raw",
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="configured_spin",
        translation_key="washer_configured_spin",
        native_unit_of_measurement="rpm",
        icon="mdi:rotate-right",
    ),
    SensorEntityDescription(
        key="configured_temperature",
        translation_key="washer_configured_temperature",
        icon="mdi:thermometer-cog",
    ),
    SensorEntityDescription(
        key="dry_setting",
        translation_key="washer_dry_setting",
        icon="mdi:tumble-dryer",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    ac_coordinators = [c for c in coordinators.values() if c.device_type == "空调"]

    sensors = [
        HisenseACEnergySensor(coordinator, desc)
        for coordinator in ac_coordinators
        for desc in AC_ENERGY_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(sensors)

    washer_coordinators = [
        coordinator
        for coordinator in coordinators.values()
        if coordinator.device_type == "洗衣机"
    ]
    async_add_entities(
        HisenseWasherSensor(coordinator, description)
        for coordinator in washer_coordinators
        for description in WASHER_SENSOR_DESCRIPTIONS
    )
    async_add_entities(
        HisenseWasherProtocolSensor(coordinator)
        for coordinator in washer_coordinators
    )


class HisenseWasherSensor(HisenseEntity, SensorEntity):
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
    def native_value(self):
        return self.status.get(self.entity_description.key)


class HisenseWasherProtocolSensor(HisenseEntity, SensorEntity):
    """Expose a sanitized read-only washer protocol snapshot."""

    _attr_translation_key = "washer_protocol_debug"
    _attr_icon = "mdi:washing-machine"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator):
        super().__init__(
            coordinator,
            "washer_protocol_debug",
            "washer_protocol_debug",
        )

    @property
    def native_value(self):
        return self.status.get("protocol_payload_sha256", "")[:12]

    @property
    def extra_state_attributes(self):
        return {
            "payload_length": self.status.get("protocol_payload_length", 0),
            "changed_indices": self.status.get("protocol_changed_indices", []),
            "nonzero_values": self.status.get("protocol_nonzero_values", {}),
            "read_only_debug": True,
        }


class HisenseACEnergySensor(HisenseEntity, SensorEntity):
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
        return self.status.get(self.entity_description.key) is not None

    @property
    def native_value(self):
        return self.status.get(self.entity_description.key)

    @property
    def last_reset(self) -> datetime:
        """The App values are cumulative for the current local calendar day."""
        return dt_util.start_of_local_day()
