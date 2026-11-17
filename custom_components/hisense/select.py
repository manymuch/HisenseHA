"""Refrigerator selects with options derived from reported model capabilities."""

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity
from .fridge_const import VARIATION_TEMP_SPACE_VALUES, WORK_MODE_LABELS

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
