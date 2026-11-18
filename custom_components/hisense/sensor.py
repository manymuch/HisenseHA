from __future__ import annotations

from datetime import datetime
from typing import Any

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

AC_HUMIDITY_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="humidity",
    translation_key="ac_humidity",
    native_unit_of_measurement="%",
    device_class=SensorDeviceClass.HUMIDITY,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:water-percent",
)

TV_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="volume",
        translation_key="tv_volume",
        icon="mdi:volume-high",
    ),
    SensorEntityDescription(
        key="source",
        translation_key="tv_source",
        icon="mdi:video-input-hdmi",
    ),
    SensorEntityDescription(
        key="last_key",
        translation_key="tv_last_key",
        icon="mdi:remote",
        entity_category=EntityCategory.DIAGNOSTIC,
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
    SensorEntityDescription(
        key="wash_time",
        translation_key="washer_wash_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:clock-outline",
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

OVEN_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="real_temperature",
        translation_key="oven_real_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="target_temperature",
        translation_key="oven_target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-chevron-up",
    ),
    SensorEntityDescription(
        key="cook_time",
        translation_key="oven_cook_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="remaining_minutes",
        translation_key="oven_remaining_minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:progress-clock",
    ),
    SensorEntityDescription(
        key="probe_temperature",
        translation_key="oven_probe_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-probe",
    ),
    SensorEntityDescription(
        key="run_status_label",
        translation_key="oven_run_status",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="work_mode_label",
        translation_key="oven_work_mode",
        icon="mdi:stove",
    ),
)

DISHWASHER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="phase_label",
        translation_key="dishwasher_phase",
        icon="mdi:dishwasher",
    ),
    SensorEntityDescription(
        key="work_mode_label",
        translation_key="dishwasher_work_mode",
        icon="mdi:tune",
    ),
    SensorEntityDescription(
        key="remaining_minutes",
        translation_key="dishwasher_remaining_minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:progress-clock",
    ),
)

WATER_HEATER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="real_temperature",
        translation_key="water_heater_real_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-water",
    ),
    SensorEntityDescription(
        key="target_temperature",
        translation_key="water_heater_target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-chevron-up",
    ),
    SensorEntityDescription(
        key="hot_water_quantity",
        translation_key="water_heater_hot_water_quantity",
        icon="mdi:water-percent",
    ),
)

HOOD_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="fan_speed_label",
        translation_key="hood_fan_speed",
        icon="mdi:fan",
    ),
    SensorEntityDescription(
        key="delay_off_remain_time",
        translation_key="hood_delay_off_remain_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-sand",
    ),
)

STOVE_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="left_fire_power",
        translation_key="stove_left_fire_power",
        icon="mdi:fire",
    ),
    SensorEntityDescription(
        key="right_fire_power",
        translation_key="stove_right_fire_power",
        icon="mdi:fire",
    ),
    SensorEntityDescription(
        key="left_timer",
        translation_key="stove_left_timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="right_timer",
        translation_key="stove_right_timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-outline",
    ),
)

DEHUMIDIFIER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="real_humidity",
        translation_key="dehumidifier_real_humidity",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="target_humidity",
        translation_key="dehumidifier_target_humidity",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.HUMIDITY,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="work_mode_label",
        translation_key="dehumidifier_work_mode",
        icon="mdi:tune",
    ),
)

FRESH_AIR_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="fan_speed",
        translation_key="fresh_air_fan_speed",
        icon="mdi:fan",
    ),
    SensorEntityDescription(
        key="work_mode_label",
        translation_key="fresh_air_work_mode",
        icon="mdi:air-filter",
    ),
)

WINE_CABINET_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="zone1_real_temperature",
        translation_key="wine_cabinet_zone1_real_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="zone1_target_temperature",
        translation_key="wine_cabinet_zone1_target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-chevron-up",
    ),
    SensorEntityDescription(
        key="zone2_real_temperature",
        translation_key="wine_cabinet_zone2_real_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="zone2_target_temperature",
        translation_key="wine_cabinet_zone2_target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-chevron-up",
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="wine_cabinet_humidity",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
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
    for coordinator in ac_coordinators:
        _add_ac_humidity_sensor(coordinator, async_add_entities)

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
        if getattr(coordinator, "device_type", None) == "干衣机"
    ]
    async_add_entities(
        HisenseDryerSensor(coordinator, description)
        for coordinator in dryer_coordinators
        for description in DRYER_SENSOR_DESCRIPTIONS
    )

    tv_coordinators = [
        coordinator
        for coordinator in coordinators.values()
        if getattr(coordinator, "device_type", None) == "电视"
    ]
    async_add_entities(
        HisenseTVSensor(coordinator, description)
        for coordinator in tv_coordinators
        for description in TV_SENSOR_DESCRIPTIONS
    )

    oven_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "烤箱"]
    async_add_entities(
        HisenseApplianceSensor(c, d) for c in oven_coordinators for d in OVEN_SENSOR_DESCRIPTIONS
    )

    dishwasher_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "洗碗机"]
    async_add_entities(
        HisenseApplianceSensor(c, d) for c in dishwasher_coordinators for d in DISHWASHER_SENSOR_DESCRIPTIONS
    )

    water_heater_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "热水器"]
    async_add_entities(
        HisenseApplianceSensor(c, d) for c in water_heater_coordinators for d in WATER_HEATER_SENSOR_DESCRIPTIONS
    )

    hood_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "油烟机"]
    async_add_entities(
        HisenseApplianceSensor(c, d) for c in hood_coordinators for d in HOOD_SENSOR_DESCRIPTIONS
    )

    stove_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "燃气灶"]
    async_add_entities(
        HisenseApplianceSensor(c, d) for c in stove_coordinators for d in STOVE_SENSOR_DESCRIPTIONS
    )

    dehumidifier_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "除湿机"]
    async_add_entities(
        HisenseApplianceSensor(c, d) for c in dehumidifier_coordinators for d in DEHUMIDIFIER_SENSOR_DESCRIPTIONS
    )

    fresh_air_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "新风系统"]
    async_add_entities(
        HisenseApplianceSensor(c, d) for c in fresh_air_coordinators for d in FRESH_AIR_SENSOR_DESCRIPTIONS
    )

    wine_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "酒柜"]
    async_add_entities(
        HisenseApplianceSensor(c, d) for c in wine_coordinators for d in WINE_CABINET_SENSOR_DESCRIPTIONS
    )

    valid_coordinators = [
        c for c in coordinators.values()
        if hasattr(c, "client") and hasattr(c.client, "device_id")
    ]
    async_add_entities(
        HisensePushMessageSensor(coordinator)
        for coordinator in valid_coordinators
    )


def _add_ac_humidity_sensor(coordinator, async_add_entities):
    """Add humidity sensor only when reported by AC."""
    if coordinator.__dict__.get("_ac_humidity_sensor_added"):
        return
    status = coordinator.data or coordinator.client.get_status()
    if status.get("humidity") is not None:
        coordinator.__dict__["_ac_humidity_sensor_added"] = True
        async_add_entities([HisenseACHumiditySensor(coordinator, AC_HUMIDITY_SENSOR_DESCRIPTION)])
        return

    remove_listener = None

    def _on_update():
        if remove_listener is not None:
            remove_listener()
        _add_ac_humidity_sensor(coordinator, async_add_entities)

    remove_listener = coordinator.async_add_listener(_on_update)


class HisenseACHumiditySensor(HisenseEntity, SensorEntity):
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
        return self.status.get("humidity")


class HisenseTVSensor(HisenseEntity, SensorEntity):
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
            return any(self.status.get(key) is not None for key in (
                "smart_mode", "quick_cooling_mode", "daily_mode",
                "super_frozen_mode", "holiday_mode",
            ))
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
        return self.client.work_mode_label

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


class HisensePushMessageSensor(HisenseEntity, SensorEntity):
    """Expose the latest received push notification message and history."""

    _attr_translation_key = "last_push_message"
    _attr_icon = "mdi:bell-ring-outline"
    _attr_available_offline = True

    def __init__(self, coordinator) -> None:
        super().__init__(
            coordinator,
            "last_push_message",
            "last_push_message",
            "mdi:bell-ring-outline",
        )
        self._attr_name = "最新推送内容"

    @property
    def native_value(self) -> str:
        push_info = getattr(self.coordinator, "last_push", None)
        if not push_info or not isinstance(push_info, dict):
            return "就绪 (监听推送中)"
        return push_info.get("summary") or push_info.get("status") or "收到新推送"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        push_info = getattr(self.coordinator, "last_push", None)
        history = getattr(self.coordinator, "push_history", [])
        attrs: dict[str, Any] = {
            "total_pushes_received": len(history),
            "recent_history": list(reversed(history[-10:])),
        }
        if isinstance(push_info, dict):
            attrs.update({
                "last_received_at": push_info.get("timestamp"),
                "status": push_info.get("status"),
                "action": push_info.get("action"),
                "business_tag": push_info.get("businessTag"),
                "device_id": push_info.get("deviceId"),
                "raw_payload": push_info.get("raw"),
            })
        return attrs


class HisenseApplianceSensor(HisenseEntity, SensorEntity):
    """通用家电传感器实体（蒸烤箱/洗碗机/热水器/油烟机/燃气灶/除湿机/新风/酒柜）."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription):
        super().__init__(coordinator, description.key, description.key, description.icon)
        self.entity_description = description

    @property
    def native_value(self):
        return self.status.get(self.entity_description.key)

