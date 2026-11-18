"""Refrigerator selects with options derived from reported model capabilities."""

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity
from .fridge_const import VARIATION_TEMP_SPACE_VALUES, WORK_MODE_LABELS
from .pyhisenseapi import (
    WASHER_PROGRAM_MAP,
    WASHER_PROGRAM_REVERSE_MAP,
    WASHER_DOSAGE_MAP,
    WASHER_DOSAGE_REVERSE_MAP,
    WASHER_SPIN_MAP,
    WASHER_SPIN_REVERSE_MAP,
    WASHER_TEMP_MAP,
    WASHER_TEMP_REVERSE_MAP,
    WASHER_RINSE_MAP,
    WASHER_RINSE_REVERSE_MAP,
    WASHER_DRY_MAP,
    WASHER_DRY_REVERSE_MAP,
    OVEN_MODE_MAP,
    OVEN_MODE_REVERSE_MAP,
    DISHWASHER_PROGRAM_MAP,
    DISHWASHER_PROGRAM_REVERSE_MAP,
    HOOD_SPEED_MAP,
    HOOD_SPEED_REVERSE_MAP,
    DEHUMIDIFIER_MODE_MAP,
    DEHUMIDIFIER_MODE_REVERSE_MAP,
    FRESH_AIR_MODE_MAP,
    FRESH_AIR_MODE_REVERSE_MAP,
    WATER_HEATER_MODES,
    WATER_HEATER_MODE_TO_ID,
    WATER_HEATER_MODE_REVERSE_MAP,
)

WASHER_SPIN_OPTIONS = list(WASHER_SPIN_MAP.keys())
WASHER_TEMP_OPTIONS = list(WASHER_TEMP_MAP.keys())
WASHER_RINSE_OPTIONS = list(WASHER_RINSE_MAP.keys())
WASHER_DRY_OPTIONS = list(WASHER_DRY_MAP.keys())

WASHER_PROGRAM_OPTIONS = list(WASHER_PROGRAM_MAP.keys())
WASHER_DOSAGE_OPTIONS = list(WASHER_DOSAGE_MAP.keys())

WASHER_WASH_TIME_OPTIONS = [
    f"{m}分钟"
    for m in (
        8, 13, 18, 22, 23, 24, 27, 28, 29, 30, 31, 32, 33, 34, 35,
        36, 37, 38, 39, 40, 41, 44, 45, 46, 47, 48, 49, 50, 51, 52,
        53, 54, 55, 56, 57, 58, 59, 60, 62, 64, 65, 66, 67, 70, 71,
        72, 75, 76, 77, 80, 81, 82, 85, 91, 92, 97
    )
]
WASHER_SOFTBAKING_OPTIONS = ["关闭", "开启"]

DRYER_PROGRAM_MAP = {
    "智能烘": 0,
    "棉麻": 1,
    "化纤": 2,
    "羊毛": 5,
    "羽绒": 6,
    "空气洗": 8,
    "热风烘": 10,
    "冷风烘": 11,
    "定时烘": 12,
}
DRYER_PROGRAM_REVERSE_MAP = {v: k for k, v in DRYER_PROGRAM_MAP.items()}
DRYER_PROGRAM_OPTIONS = list(DRYER_PROGRAM_MAP.keys())

OVEN_MODE_OPTIONS = list(OVEN_MODE_MAP.keys())
DISHWASHER_PROGRAM_OPTIONS = list(DISHWASHER_PROGRAM_MAP.keys())
HOOD_SPEED_OPTIONS = list(HOOD_SPEED_MAP.keys())
DEHUMIDIFIER_MODE_OPTIONS = list(DEHUMIDIFIER_MODE_MAP.keys())
FRESH_AIR_MODE_OPTIONS = list(FRESH_AIR_MODE_MAP.keys())


def _safe_lookup_option(val, reverse_map, options_list, fallback_prefix="模式"):
    if val is None:
        return None
    # 1. 直接查反向映射
    res = reverse_map.get(val)
    if res is not None:
        return res
    # 2. 尝试转成整数查找
    if str(val).isdigit():
        res = reverse_map.get(int(val))
        if res is not None:
            return res
    # 3. 尝试转成字符串查找
    res = reverse_map.get(str(val))
    if res is not None:
        return res
    # 4. 如果值本身已经在合法选项列表中
    if str(val) in options_list:
        return str(val)
    # 5. 无法识别的未知模式/程序，生成安全兜底名称
    return f"{fallback_prefix} {val}"


#: 「自定义」= 退出正在运行的预设模式（下发 value="0"），不是只读展示值。
CUSTOM_MODE = "自定义"
#: 预设模式选项（与小程序 / App 一致）。
WORK_MODE_OPTIONS = ["智能", "速冷", CUSTOM_MODE]
#: 变温空间选项，顺序与数值对应：0 原鲜 / 1 0℃养鲜 / 2 母婴
VARIATION_MODE_OPTIONS = [
    VARIATION_TEMP_SPACE_VALUES[0],
    VARIATION_TEMP_SPACE_VALUES[1],
    VARIATION_TEMP_SPACE_VALUES[2],
]

#: 两个 select 都是日常控制项，因此归在主（控制）分类，不设 entity_category。
FRIDGE_SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="work_mode_select",
        translation_key="fridge_work_mode_select",
        options=WORK_MODE_OPTIONS,
        icon="mdi:tune",
    ),
    SelectEntityDescription(
        key="variation_mode_select",
        translation_key="fridge_variation_mode_select",
        options=VARIATION_MODE_OPTIONS,
        icon="mdi:tune",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    fridge_coordinators = [
        c for c in coordinators.values() if c.device_type == "冰箱"
    ]

    entities = [
        HisenseFridgeModeSelect(coordinator, desc)
        for coordinator in fridge_coordinators
        for desc in FRIDGE_SELECT_DESCRIPTIONS
    ]
    async_add_entities(entities)

    washer_coordinators = [
        c for c in coordinators.values() if c.device_type == "洗衣机"
    ]
    washer_entities = [
        select_cls(coordinator)
        for coordinator in washer_coordinators
        for select_cls in (
            HisenseWasherProgramSelect,
            HisenseWasherDetergentSelect,
            HisenseWasherSoftenSelect,
            HisenseWasherTemperatureSelect,
            HisenseWasherWashTimeSelect,
            HisenseWasherRinseSelect,
            HisenseWasherSpinSelect,
            HisenseWasherDrySelect,
            HisenseWasherSoftbakingSelect,
        )
    ]
    if washer_entities:
        async_add_entities(washer_entities)

    dryer_coordinators = [
        c for c in coordinators.values() if c.device_type == "干衣机"
    ]
    if dryer_coordinators:
        async_add_entities([HisenseDryerProgramSelect(c) for c in dryer_coordinators])

    oven_coordinators = [c for c in coordinators.values() if c.device_type == "烤箱"]
    if oven_coordinators:
        async_add_entities([HisenseOvenModeSelect(c) for c in oven_coordinators])

    dishwasher_coordinators = [c for c in coordinators.values() if c.device_type == "洗碗机"]
    if dishwasher_coordinators:
        async_add_entities([HisenseDishwasherProgramSelect(c) for c in dishwasher_coordinators])

    hood_coordinators = [c for c in coordinators.values() if c.device_type == "油烟机"]
    if hood_coordinators:
        async_add_entities([HisenseHoodSpeedSelect(c) for c in hood_coordinators])

    dehumidifier_coordinators = [c for c in coordinators.values() if c.device_type == "除湿机"]
    if dehumidifier_coordinators:
        async_add_entities([HisenseDehumidifierModeSelect(c) for c in dehumidifier_coordinators])

    fresh_air_coordinators = [c for c in coordinators.values() if c.device_type == "新风系统"]
    if fresh_air_coordinators:
        async_add_entities([HisenseFreshAirModeSelect(c) for c in fresh_air_coordinators])

    water_heater_coordinators = [c for c in coordinators.values() if c.device_type == "热水器"]
    if water_heater_coordinators:
        async_add_entities([HisenseWaterHeaterModeSelect(c) for c in water_heater_coordinators])


class HisenseFridgeModeSelect(HisenseEntity, SelectEntity):
    entity_description: SelectEntityDescription

    def __init__(self, coordinator, description: SelectEntityDescription):
        super().__init__(
            coordinator, description.key, description.key, description.icon
        )
        self.entity_description = description

    @property
    def options(self):
        if self.entity_description.key == "work_mode_select":
            return [
                WORK_MODE_LABELS[mode] for mode in self.client.supported_work_modes
            ] + [CUSTOM_MODE]
        return list(self.client.variation_options.values())

    @property
    def current_option(self) -> str | None:
        if self.entity_description.key == "work_mode_select":
            return self.client.work_mode_label
        return self.status.get("variation_mode")

    async def async_select_option(self, option: str) -> None:
        if self.entity_description.key == "work_mode_select":
            if option == CUSTOM_MODE:
                # 「自定义」= 退出正在运行的预设模式（SetModes.* 发 value="0"）。
                # 只关闭当前激活的预设模式；设定温度不受影响，
                # 模式关掉后 displayTemperature 自动回落到用户原来的设定值。
                ok = await self.client.clear_fridge_modes()
                label = "退出工作模式"
            else:
                ok = await self.client.select_fridge_mode(option)
                label = "工作模式"
        else:
            ok = await self.client.set_variation_mode(option)
            label = "变温空间"
        if ok:
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(
            f"Failed to set Hisense fridge {label} to {option}"
        )


class HisenseWasherProgramSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_program_select"
    _attr_icon = "mdi:washing-machine"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_program_select", "washer_program_select", "mdi:washing-machine")
        self._attr_options = WASHER_PROGRAM_OPTIONS

    @property
    def options(self) -> list[str]:
        curr = self.current_option
        if curr is not None and curr not in self._attr_options:
            return list(self._attr_options) + [curr]
        return self._attr_options

    @property
    def current_option(self) -> str | None:
        prog_id = self.status.get("program")
        return _safe_lookup_option(prog_id, WASHER_PROGRAM_REVERSE_MAP, self._attr_options, "程序")

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节程序")
        prog_id = WASHER_PROGRAM_MAP.get(option)
        if prog_id is None:
            raise HomeAssistantError(f"Unsupported washer program: {option}")
        if await self.client.set_mode(prog_id):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set Hisense washer program to {option}")


class HisenseWasherDetergentSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_detergent_select"
    _attr_icon = "mdi:cup-water"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_detergent_select", "washer_detergent_select", "mdi:cup-water")
        self._attr_options = WASHER_DOSAGE_OPTIONS

    @property
    def current_option(self) -> str | None:
        val = str(self.status.get("detergent_mode") or "")
        return WASHER_DOSAGE_REVERSE_MAP.get(val, "100%")

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节洗涤剂投放量")
        val = WASHER_DOSAGE_MAP.get(option)
        if val is None:
            raise HomeAssistantError(f"Unsupported detergent option: {option}")
        if await self.client.set_detergent_mode(val):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set detergent mode to {option}")


class HisenseWasherSoftenSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_soften_select"
    _attr_icon = "mdi:flower"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_soften_select", "washer_soften_select", "mdi:flower")
        self._attr_options = WASHER_DOSAGE_OPTIONS

    @property
    def current_option(self) -> str | None:
        val = str(self.status.get("soften_mode") or "")
        return WASHER_DOSAGE_REVERSE_MAP.get(val, "100%")

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节柔顺剂投放量")
        val = WASHER_DOSAGE_MAP.get(option)
        if val is None:
            raise HomeAssistantError(f"Unsupported soften option: {option}")
        if await self.client.set_soften_mode(val):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set soften mode to {option}")


class HisenseWasherSpinSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_spin_select"
    _attr_icon = "mdi:rotate-right"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_spin_select", "washer_spin_select", "mdi:rotate-right")
        self._attr_options = WASHER_SPIN_OPTIONS

    @property
    def current_option(self) -> str | None:
        val = self.status.get("configured_spin")
        if val is None:
            val = self.status.get("dehydration_speed")
        if val is not None:
            return WASHER_SPIN_REVERSE_MAP.get(str(val))
        return None

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节脱水转速")
        val = WASHER_SPIN_MAP.get(option)
        if val is None:
            raise HomeAssistantError(f"Unsupported spin speed option: {option}")

        # 检查是否开启了烘干功能（烘干开启时洗衣机强制要求 1200/1400 转）
        dry_val = self.status.get("drying_method")
        if dry_val is None:
            dry_val = self.status.get("dry_value")
        is_drying_active = str(dry_val) not in ("0", "None", "")
        if is_drying_active and str(val) not in ("1200", "1400"):
            raise HomeAssistantError(
                "当前已开启烘干功能，海信洗衣机硬件安全策略要求脱水转速必须保持在 1200 转以上（可选 1200 或 1400 转）以确保烘干前有效脱水；若需设置较低转速或不脱水，请先将【烘干设定】设为【关闭】。"
            )

        if await self.client.set_spin_speed(val):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set spin speed to {option}")


class HisenseWasherTemperatureSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_temperature_select"
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_temperature_select", "washer_temperature_select", "mdi:thermometer")
        self._attr_options = WASHER_TEMP_OPTIONS

    @property
    def current_option(self) -> str | None:
        val = self.status.get("wash_temperature")
        if val is None:
            val = self.status.get("temperature_raw")
        if val is not None:
            return WASHER_TEMP_REVERSE_MAP.get(str(val))
        return None

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节洗涤水温")
        val = WASHER_TEMP_MAP.get(option)
        if val is None:
            raise HomeAssistantError(f"Unsupported temperature option: {option}")
        if await self.client.set_temperature(val):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set wash temperature to {option}")


class HisenseWasherRinseSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_rinse_select"
    _attr_icon = "mdi:water-opacity"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_rinse_select", "washer_rinse_select", "mdi:water-opacity")
        self._attr_options = WASHER_RINSE_OPTIONS

    @property
    def current_option(self) -> str | None:
        val = self.status.get("rinsing_frequency")
        if val is not None:
            return WASHER_RINSE_REVERSE_MAP.get(str(val))
        return None

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节漂洗次数")
        val = WASHER_RINSE_MAP.get(option)
        if val is None:
            raise HomeAssistantError(f"Unsupported rinse count option: {option}")
        if await self.client.set_rinse_count(val):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set rinse count to {option}")


class HisenseWasherDrySelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_dry_select"
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, coordinator):
        super().__init__(coordinator, "washer_dry_select", "washer_dry_select", "mdi:weather-sunny")
        self._attr_options = WASHER_DRY_OPTIONS

    @property
    def current_option(self) -> str | None:
        val = self.status.get("drying_method")
        if val is None:
            val = self.status.get("dry_value")
        if val is not None:
            return WASHER_DRY_REVERSE_MAP.get(str(val), "关闭")
        return "关闭"

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节烘干方式")
        val = WASHER_DRY_MAP.get(option)
        if val is None:
            raise HomeAssistantError(f"Unsupported dry mode option: {option}")
        if await self.client.set_dry_mode(val):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set dry mode to {option}")


class HisenseWasherWashTimeSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_wash_time_select"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator):
        super().__init__(
            coordinator,
            "washer_wash_time_select",
            "washer_wash_time_select",
            "mdi:clock-outline",
        )
        self._attr_options = WASHER_WASH_TIME_OPTIONS

    @property
    def options(self) -> list[str]:
        curr = self.status.get("wash_time")
        if curr is not None:
            curr_str = f"{curr}分钟"
            if curr_str not in WASHER_WASH_TIME_OPTIONS:
                nums = sorted(
                    [int(x.replace("分钟", "")) for x in WASHER_WASH_TIME_OPTIONS]
                    + [int(curr)]
                )
                return [f"{n}分钟" for n in nums]
        return WASHER_WASH_TIME_OPTIONS

    @property
    def current_option(self) -> str | None:
        val = self.status.get("wash_time")
        if val is not None:
            return f"{val}分钟"
        return None

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节洗涤时间")
        minutes = option.replace("分钟", "").strip()
        if await self.client.set_wash_time(minutes):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set wash time to {option}")


class HisenseWasherSoftbakingSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "washer_softbaking_select"
    _attr_icon = "mdi:snowflake-thermometer"

    def __init__(self, coordinator):
        super().__init__(
            coordinator,
            "washer_softbaking_select",
            "washer_softbaking_select",
            "mdi:snowflake-thermometer",
        )
        self._attr_options = WASHER_SOFTBAKING_OPTIONS

    @property
    def current_option(self) -> str:
        if self.status.get("softbaking") or self.status.get("drying_modes") == 1:
            return "开启"
        return "关闭"

    async def async_select_option(self, option: str) -> None:
        if not self.status.get("power_on"):
            raise HomeAssistantError("洗衣机已关机，请先开启洗衣机面板电源后再调节低温烘")
        enabled = option == "开启"
        cur_program = str(self.status.get("program_code", self.status.get("program", "")))
        if enabled and cur_program not in ("35", "Single_dry"):
            prog_name = self.status.get("program_name") or WASHER_PROGRAM_REVERSE_MAP.get(cur_program, "当前程序")
            raise HomeAssistantError(
                f"海信洗衣机硬件固件限制：【低温烘】属于【单烘】程序的专属烘干模式（与标准烘对应，可搭配即穿/即存或定时烘干共存）。"
                f"当前程序为【{prog_name}】，固件不支持在此程序下开启低温烘。请先在“洗衣程序”中切换为【单烘】，即可开启低温烘！"
            )
        if await self.client.set_softbaking(enabled):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set softbaking to {option}")


class HisenseDryerProgramSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "dryer_program_select"
    _attr_icon = "mdi:tumble-dryer"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dryer_program_select", "dryer_program_select")
        self._attr_options = DRYER_PROGRAM_OPTIONS

    @property
    def options(self) -> list[str]:
        curr = self.current_option
        if curr is not None and curr not in self._attr_options:
            return list(self._attr_options) + [curr]
        return self._attr_options

    @property
    def current_option(self):
        val = self.status.get("program")
        return _safe_lookup_option(val, DRYER_PROGRAM_REVERSE_MAP, self._attr_options, "程序")

    async def async_select_option(self, option: str):
        mode_id = DRYER_PROGRAM_MAP.get(option)
        if mode_id is None:
            if str(option).isdigit():
                mode_id = int(option)
            else:
                raise HomeAssistantError(f"Unsupported dryer program: {option}")
        if not self.status.get("power_on"):
            raise HomeAssistantError("请先开启干衣机电源后再切换程序")
        if await self.client.set_program(mode_id):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set dryer program to {option}")



class HisenseOvenModeSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "oven_mode_select"
    _attr_icon = "mdi:stove"

    def __init__(self, coordinator):
        super().__init__(coordinator, "oven_mode_select", "oven_mode_select", "mdi:stove")
        self._attr_options = OVEN_MODE_OPTIONS

    @property
    def options(self) -> list[str]:
        curr = self.current_option
        if curr is not None and curr not in self._attr_options:
            return list(self._attr_options) + [curr]
        return self._attr_options

    @property
    def current_option(self):
        val = self.status.get("work_mode")
        return _safe_lookup_option(val, OVEN_MODE_REVERSE_MAP, self._attr_options, "模式")

    async def async_select_option(self, option: str):
        mode_id = OVEN_MODE_MAP.get(option)
        if mode_id is None:
            if str(option).isdigit():
                mode_id = int(option)
            else:
                raise HomeAssistantError(f"Unsupported oven mode: {option}")
        if not self.status.get("power_on"):
            raise HomeAssistantError("请先开启蒸烤箱电源后再切换模式")
        if await self.client.set_mode(mode_id):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set oven mode to {option}")


class HisenseDishwasherProgramSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "dishwasher_program_select"
    _attr_icon = "mdi:dishwasher"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dishwasher_program_select", "dishwasher_program_select", "mdi:dishwasher")
        self._attr_options = DISHWASHER_PROGRAM_OPTIONS

    @property
    def options(self) -> list[str]:
        curr = self.current_option
        if curr is not None and curr not in self._attr_options:
            return list(self._attr_options) + [curr]
        return self._attr_options

    @property
    def current_option(self):
        val = self.status.get("work_mode")
        return _safe_lookup_option(val, DISHWASHER_PROGRAM_REVERSE_MAP, self._attr_options, "程序")

    async def async_select_option(self, option: str):
        mode_id = DISHWASHER_PROGRAM_MAP.get(option)
        if mode_id is None:
            if str(option).isdigit():
                mode_id = int(option)
            else:
                raise HomeAssistantError(f"Unsupported dishwasher program: {option}")
        if not self.status.get("power_on"):
            raise HomeAssistantError("请先开启洗碗机电源后再切换程序")
        if await self.client.set_program(mode_id):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set dishwasher program to {option}")


class HisenseHoodSpeedSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "hood_speed_select"
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator):
        super().__init__(coordinator, "hood_speed_select", "hood_speed_select", "mdi:fan")
        self._attr_options = HOOD_SPEED_OPTIONS

    @property
    def options(self) -> list[str]:
        curr = self.current_option
        if curr is not None and curr not in self._attr_options:
            return list(self._attr_options) + [curr]
        return self._attr_options

    @property
    def current_option(self):
        val = self.status.get("fan_speed")
        return _safe_lookup_option(val, HOOD_SPEED_REVERSE_MAP, self._attr_options, "风速")

    async def async_select_option(self, option: str):
        speed = HOOD_SPEED_MAP.get(option)
        if speed is None:
            if str(option).isdigit():
                speed = int(option)
            else:
                raise HomeAssistantError(f"Unsupported hood speed: {option}")
        if await self.client.set_fan_speed(speed):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set hood speed to {option}")


class HisenseDehumidifierModeSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "dehumidifier_mode_select"
    _attr_icon = "mdi:tune"

    def __init__(self, coordinator):
        super().__init__(coordinator, "dehumidifier_mode_select", "dehumidifier_mode_select", "mdi:tune")
        self._attr_options = DEHUMIDIFIER_MODE_OPTIONS

    @property
    def options(self) -> list[str]:
        curr = self.current_option
        if curr is not None and curr not in self._attr_options:
            return list(self._attr_options) + [curr]
        return self._attr_options

    @property
    def current_option(self):
        val = self.status.get("work_mode")
        return _safe_lookup_option(val, DEHUMIDIFIER_MODE_REVERSE_MAP, self._attr_options, "模式")

    async def async_select_option(self, option: str):
        mode_id = DEHUMIDIFIER_MODE_MAP.get(option)
        if mode_id is None:
            if str(option).isdigit():
                mode_id = int(option)
            else:
                raise HomeAssistantError(f"Unsupported dehumidifier mode: {option}")
        if not self.status.get("power_on"):
            raise HomeAssistantError("请先开启除湿机电源后再切换模式")
        if await self.client.set_mode(mode_id):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set dehumidifier mode to {option}")


class HisenseFreshAirModeSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "fresh_air_mode_select"
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator):
        super().__init__(coordinator, "fresh_air_mode_select", "fresh_air_mode_select", "mdi:air-filter")
        self._attr_options = FRESH_AIR_MODE_OPTIONS

    @property
    def options(self) -> list[str]:
        curr = self.current_option
        if curr is not None and curr not in self._attr_options:
            return list(self._attr_options) + [curr]
        return self._attr_options

    @property
    def current_option(self):
        val = self.status.get("work_mode")
        return _safe_lookup_option(val, FRESH_AIR_MODE_REVERSE_MAP, self._attr_options, "模式")

    async def async_select_option(self, option: str):
        mode_id = FRESH_AIR_MODE_MAP.get(option)
        if mode_id is None:
            if str(option).isdigit():
                mode_id = int(option)
            else:
                raise HomeAssistantError(f"Unsupported fresh air mode: {option}")
        if not self.status.get("power_on"):
            raise HomeAssistantError("请先开启新风系统电源后再切换模式")
        if await self.client.set_mode(mode_id):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set fresh air mode to {option}")


class HisenseWaterHeaterModeSelect(HisenseEntity, SelectEntity):
    _attr_translation_key = "water_heater_mode"
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator):
        super().__init__(coordinator, "water_heater_mode", "water_heater_mode")
        self._attr_options = list(WATER_HEATER_MODES.values())

    @property
    def options(self) -> list[str]:
        curr = self.current_option
        if curr is not None and curr not in self._attr_options:
            return list(self._attr_options) + [curr]
        return self._attr_options

    @property
    def current_option(self):
        val = self.status.get("work_mode")
        return _safe_lookup_option(val, WATER_HEATER_MODE_REVERSE_MAP, self._attr_options, "模式")

    async def async_select_option(self, option: str):
        mode_id = WATER_HEATER_MODE_TO_ID.get(option)
        if mode_id is None:
            if str(option).isdigit():
                mode_id = int(option)
            else:
                raise HomeAssistantError(f"Unsupported water heater mode: {option}")
        if not self.status.get("power_on"):
            await self.client.turn_on()
        if await self.client.set_mode(mode_id):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError(f"Failed to set water heater mode to {option}")

