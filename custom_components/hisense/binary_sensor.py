"""Binary sensors for Hisense devices.

Washer/dryer expose power/door-lock/child-lock flags. The fridge derives its
sensors from the ``detail`` named-state map:

* one ``problem`` sensor per supported alarm key. Door-open flags are alarms in
  this protocol (``*OpenDoorAlarm``), so they are exposed here and nowhere
  else. Alarms are device state, not integration diagnostics, so they stay in
  the primary group — ``EntityCategory.DIAGNOSTIC`` is reserved for things you
  only look at while troubleshooting.

Every alarm key known to the protocol gets an entity at setup time, without
waiting for the first cloud read: waiting meant an offline fridge at HA startup
lost all alarm entities until reload. Once a full ``states`` response arrives
the keys are split by what the device actually said:

* ``"--"`` — the model does not have this alarm. The entity goes
  ``unavailable`` and is disabled in the entity registry, so 11 of this
  model's 16 alarm bits do not clutter the dashboard.
* key absent — the response was incomplete. The entity goes ``unavailable``
  for that cycle only; it is never disabled, and recovers on the next read.
"""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .entity import HisenseEntity
from .fridge_const import FRIDGE_ALARM_CODES

#: Canonical alarm key list (the shared dict's insertion order).
ALARM_KEYS: tuple[str, ...] = tuple(FRIDGE_ALARM_CODES)

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

#: 冰箱的整机级只读布尔量。与逐项告警位不同，这几个键是通用的，
#: 任何机型只要上云就会报，因此不需要做 "--" 支持性探测。
FRIDGE_FLAG_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    # 云连接状态。注意它比"HTTP 请求成功"更真实：接口能通不等于冰箱在线。
    BinarySensorEntityDescription(
        key="online",
        translation_key="fridge_connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:cloud-check",
    ),
    # 冰箱运行开关。只能读不能控（App 无开关机入口，Power 类命令均 notSupported）。
    BinarySensorEntityDescription(
        key="power_on",
        translation_key="fridge_power",
        device_class=BinarySensorDeviceClass.POWER,
        icon="mdi:power",
    ),
    # 除菌运行中（dBDDegerming）。与 switch.fridge_degerming 同源，但语义不同：
    # 那个是可写控制入口，这个是只读状态 —— 除菌跑完会自己停，也可能由设备
    # 按内部计划自动启动，只想「看它是否在跑」时读这个，不必去读一个开关。
    BinarySensorEntityDescription(
        key="degerming_active",
        translation_key="fridge_degerming_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:shield-sun",
    ),
    # 净味（「离子除菌净味系统」的独立位）。开除菌后它会跟着变 1，但关除菌
    # 不会回到 0，所以它表达的是「净味功能是否开着」，不能用来判断除菌是否在跑
    # —— 后者看 degerming_active（绑 dBDDegerming）。
    # 少数机型不报这个键（"0" 也可能是占位默认值），缺失时实体显示 unavailable。
    BinarySensorEntityDescription(
        key="cleaner_switch",
        translation_key="fridge_cleaner",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:air-purifier",
    ),
)


def _fridge_alarm_description(code: str) -> BinarySensorEntityDescription:
    return BinarySensorEntityDescription(
        key=f"alarm_{code}",
        translation_key=f"fridge_alarm_{code}",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle",
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

    fridge_coordinators = [
        coordinator
        for coordinator in coordinators.values()
        if coordinator.device_type == "冰箱"
    ]
    for coordinator in fridge_coordinators:
        _add_fridge_entities(coordinator, async_add_entities)


def _add_fridge_entities(coordinator, async_add_entities):
    """Create the fridge flags and one entity per known alarm key."""
    if coordinator.__dict__.get("_fridge_bs_added"):
        return
    coordinator.__dict__["_fridge_bs_added"] = True
    async_add_entities(
        HisenseFridgeFlagSensor(coordinator, description)
        for description in FRIDGE_FLAG_DESCRIPTIONS
    )
    async_add_entities(
        HisenseFridgeAlarmSensor(coordinator, _fridge_alarm_description(code))
        for code in ALARM_KEYS
    )


class HisenseFridgeFlagSensor(HisenseEntity, BinarySensorEntity):
    """A single whole-device boolean from the ``detail`` states map.

    Used for connectivity (``onlineStatus``) and power (``refrigeratorOn``).
    Both are read-only: the fridge exposes no command for them, so there is
    deliberately no ``turn_on``/``turn_off``.
    """

    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, description: BinarySensorEntityDescription):
        super().__init__(
            coordinator, description.key, description.key, description.icon
        )
        self.entity_description = description
        if description.entity_category is not None:
            self._attr_entity_category = description.entity_category
        # 连通性实体必须在断网/离线时依旧可用，否则它只会显示"不可用"，
        # 反而说不出"设备当前离线"这个事实。
        if description.key == "online":
            self._attr_available_offline = True

    @property
    def available(self) -> bool:
        if self._attr_available_offline:
            return True
        # A model that does not report the key should read as unavailable,
        # not as "off".
        return super().available and self.status.get(self.entity_description.key) is not None

    @property
    def is_on(self) -> bool | None:
        if (
            self.entity_description.key == "online"
            and not self.coordinator.last_update_success
        ):
            # 只有连通性实体能凭"读不到云端"断言不可达；其余状态位保留上一次
            # 读到的值，与 sensor/number 的策略一致（数据有多旧看上次更新时间）。
            return None if self.coordinator.data is None else False
        value = self.status.get(self.entity_description.key)
        return None if value is None else bool(value)


class HisenseFridgeAlarmSensor(HisenseEntity, BinarySensorEntity):
    """Problem sensor for one fridge alarm flag."""

    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, description: BinarySensorEntityDescription):
        super().__init__(
            coordinator, description.key, description.key, description.icon
        )
        self.entity_description = description
        # EntityDescription 上的分类需要显式落到实体属性，否则不会生效。
        if description.entity_category is not None:
            self._attr_entity_category = description.entity_category

    @property
    def _code(self) -> str:
        return self.entity_description.key.removeprefix("alarm_")

    @property
    def _unsupported(self) -> bool:
        """Return True only when the model explicitly reports ``"--"``.

        A key missing from a partial response is *unknown*, never unsupported —
        treating it as unsupported would let one bad read disable the entity for
        good.
        """
        return self._code in (self.status.get("unsupported_alarms") or [])

    @property
    def _missing(self) -> bool:
        return self._code in (self.status.get("missing_alarms") or [])

    @property
    def available(self) -> bool:
        """Stay available until the device proves it lacks this alarm bit.

        ``unsupported_alarms`` / ``missing_alarms`` only exist after a full
        ``states`` read, so before the first successful read every alarm entity
        is created and simply reports ``unknown``.
        """
        if not super().available:
            return False
        if (
            self.status.get("unsupported_alarms") is None
            and self.status.get("missing_alarms") is None
        ):
            # 还没有完整 states：支持性未知，先当作可用（状态 unknown）。
            return True
        return not self._unsupported and not self._missing

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # 本次 add 完成后再动注册表：写 disabled_by 会让 HA 立刻移除该实体，
        # 在 add 过程中做会撞上平台自己还没登记完的窗口。
        if self._unsupported:
            self.hass.async_create_task(self._async_disable_if_unsupported())

    async def _async_disable_if_unsupported(self) -> None:
        self._disable_if_unsupported()

    def _handle_coordinator_update(self) -> None:
        self._disable_if_unsupported()
        super()._handle_coordinator_update()

    def _disable_if_unsupported(self) -> None:
        """Disable the entity in the registry once the model proves it lacks it.

        Setup cannot know which alarm bits exist (that is why all of them are
        created up front), so the decision is made once a full ``states`` read
        reports ``"--"``. Only ``"--"`` counts: a key that is merely absent from
        a partial response must stay enabled.

        Three guards:

        * never touch an entry the user disabled or re-enabled by hand
          (``disabled_by`` already set);
        * only write once — ``async_update_entity`` fires a registry event, and
          HA then removes the live entity from the state machine;
        * never disable for ``missing_alarms``.
        """
        if not self._unsupported or getattr(self, "hass", None) is None:
            return
        registry = er.async_get(self.hass)
        entry = registry.async_get(self.entity_id)
        if entry is None or entry.disabled_by is not None:
            return
        registry.async_update_entity(
            self.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
        )

    @property
    def is_on(self) -> bool | None:
        states = self.status.get("alarm_states") or {}
        if self._code not in states:
            return None
        return states[self._code]

    @property
    def extra_state_attributes(self):
        return {"alarm_label": FRIDGE_ALARM_CODES.get(self._code, self._code)}


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
