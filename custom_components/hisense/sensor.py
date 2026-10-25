from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfTemperature, UnitOfTime
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

DRYER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="machine_state",
        translation_key="dryer_run_state",
        icon="mdi:tumble-dryer",
    ),
    SensorEntityDescription(
        key="program",
        translation_key="dryer_program",
        icon="mdi:format-list-numbered",
    ),
    SensorEntityDescription(
        key="remaining_minutes",
        translation_key="dryer_remaining_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="dry_level",
        translation_key="dryer_dry_level",
        icon="mdi:water-minus-outline",
    ),
    SensorEntityDescription(
        key="dry_temperature",
        translation_key="dryer_dry_temperature",
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="drying_method",
        translation_key="dryer_drying_method",
        icon="mdi:fan",
    ),
    SensorEntityDescription(
        key="fault",
        translation_key="dryer_fault",
        icon="mdi:alert-circle-outline",
    ),
)

FRIDGE_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="refrigerator_real_temperature",
        translation_key="fridge_refrigerator_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fridge-top",
    ),
    SensorEntityDescription(
        key="freezer_real_temperature",
        translation_key="fridge_freezer_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:snowflake-thermometer",
    ),
    SensorEntityDescription(
        key="variation_mode",
        translation_key="fridge_variation_mode",
        icon="mdi:tune",
    ),
    SensorEntityDescription(
        key="work_mode",
        translation_key="fridge_work_mode",
        icon="mdi:format-list-bulleted",
    ),
    SensorEntityDescription(
        key="compressor_frequency",
        translation_key="fridge_compressor_frequency",
        native_unit_of_measurement="Hz",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    #: 「生效温度」= 模式覆盖之后真正执行的温度。开智能/速冷时设定值不变，
    #: 变的只有这个，所以它不是诊断信息，而是冰箱当前的实际工作目标。
    SensorEntityDescription(
        key="display_refrigerator_temperature",
        translation_key="fridge_refrigerator_display_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fridge-top",
    ),
    SensorEntityDescription(
        key="display_freezer_temperature",
        translation_key="fridge_freezer_display_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:snowflake-thermometer",
    ),
    #: 上次数据更新时间：优先取云端 ``reportTime``（设备最后一次上报的时刻），
    #: 缺失时退回本机成功拉取的时刻。放在诊断区，用来判断「刚才那个门状态
    #: 到底是刚发生的还是两小时前的」。
    SensorEntityDescription(
        key="data_updated",
        translation_key="fridge_data_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-check-outline",
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

    fridge_coordinators = [
        c for c in coordinators.values() if c.device_type == "冰箱"
    ]
    async_add_entities(
        HisenseFridgeSensor(coordinator, description)
        for coordinator in fridge_coordinators
        for description in FRIDGE_SENSOR_DESCRIPTIONS
    )

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

    dryer_coordinators = [
        coordinator
        for coordinator in coordinators.values()
        if coordinator.device_type == "干衣机"
    ]
    async_add_entities(
        HisenseDryerSensor(coordinator, description)
        for coordinator in dryer_coordinators
        for description in DRYER_SENSOR_DESCRIPTIONS
    )


class HisenseFridgeSensor(HisenseEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription):
        super().__init__(
            coordinator, description.key, description.key, description.icon
        )
        self.entity_description = description
        # EntityDescription 上的分类/默认启用开关需要显式落到实体属性上。
        if description.entity_category is not None:
            self._attr_entity_category = description.entity_category
        if description.entity_registry_enabled_default is False:
            self._attr_entity_registry_enabled_default = False
        if description.key == "data_updated":
            # 云端读不到、设备离线时，这个实体恰恰最有用（告诉你手里的数据
            # 有多旧），所以不参与可用性闸门，始终可读。
            self._attr_available_offline = True

    @property
    def available(self) -> bool:
        # 先过基类闸门（设备是否在线），再判断本机是否上报该键，
        # 否则缺失的键会显示成 0 而不是不可用。
        if not super().available:
            return False
        key = self.entity_description.key
        if key == "work_mode":
            # Needs at least one mode bit to say anything meaningful.
            return (
                self.status.get("smart_mode") is not None
                or self.status.get("quick_cooling_mode") is not None
            )
        if key in (
            "compressor_frequency",
            "display_refrigerator_temperature",
            "display_freezer_temperature",
        ):
            # 少数机型不报这些键，缺失时显示为不可用而非 0。
            return self.status.get(key) is not None
        return True

    @property
    def native_value(self):
        key = self.entity_description.key
        if key == "work_mode":
            return self._work_mode_label()
        if key == "data_updated":
            return self._data_updated()
        return self.status.get(key)

    def _data_updated(self) -> datetime | None:
        """Return when the current data was produced.

        ``reportTime`` is the device's own last-reported timestamp and is the
        honest answer to "how old is what I'm looking at" — it stops moving
        when the fridge goes offline. It is a naive local string, so interpret
        it in HA's configured time zone. Models that don't report it fall back
        to the last successful cloud read.
        """
        raw = self.status.get("report_time")
        parsed = dt_util.parse_datetime(raw) if isinstance(raw, str) else None
        if parsed is None:
            return self.coordinator.last_success_time
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return parsed

    def _work_mode_label(self) -> str:
        if self.status.get("quick_cooling_mode"):
            return "速冷"
        if self.status.get("smart_mode"):
            return "智能"
        return "自定义"

    @property
    def extra_state_attributes(self):
        key = self.entity_description.key
        if key == "variation_mode":
            return {"variation_mode_id": self.status.get("variation_mode_id")}
        if key == "data_updated":
            last_read = self.coordinator.last_success_time
            return {
                "report_time": self.status.get("report_time"),
                "last_read_time": (
                    last_read.isoformat() if last_read is not None else None
                ),
            }
        return None


class HisenseDryerSensor(HisenseEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription):
        super().__init__(coordinator, description.key, description.key, description.icon)
        self.entity_description = description

    @property
    def native_value(self):
        return self.status.get(self.entity_description.key)


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
        # 云端读取失败时保留上一次的值，不要整片变 unavailable。
        return self.status.get(self.entity_description.key) is not None

    @property
    def native_value(self):
        return self.status.get(self.entity_description.key)

    @property
    def last_reset(self) -> datetime:
        """The App values are cumulative for the current local calendar day."""
        return dt_util.start_of_local_day()
