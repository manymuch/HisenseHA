import asyncio

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity

WORK_MODE_OPTIONS = ["智能", "速冷"]
VARIATION_MODE_OPTIONS = ["母婴", "0℃养鲜", "原鲜"]

WORK_MODE_MAP = {
    "智能": 64,
    "速冷": 65,
}

VARIATION_MODE_MAP = {
    "母婴": 64,
    "0℃养鲜": 32,
    "原鲜": 16,
}

FRIDGE_SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="work_mode_select",
        translation_key="work_mode_select",
        options=WORK_MODE_OPTIONS,
        icon="mdi:format-list-bulleted",
    ),
    SelectEntityDescription(
        key="variation_mode_select",
        translation_key="variation_mode_select",
        options=VARIATION_MODE_OPTIONS,
        icon="mdi:format-list-bulleted",
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
        super().__init__(coordinator, description.key, description.key, description.icon)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return True

    @property
    def options(self) -> list[str]:
        if self.entity_description.key == "work_mode_select":
            current_mode = self.status.get("work_mode")
            if current_mode == "自定义" and current_mode not in WORK_MODE_OPTIONS:
                return WORK_MODE_OPTIONS + ["自定义"]
        return self.entity_description.options

    @property
    def current_option(self) -> str | None:
        if self.entity_description.key == "work_mode_select":
            return self.status.get("work_mode")
        return self.status.get("variation_mode")

    async def async_select_option(self, option: str) -> None:
        if self.entity_description.key == "work_mode_select":
            mode_id = WORK_MODE_MAP.get(option)
            if mode_id is None:
                raise HomeAssistantError(f"无效的工作模式选项: {option}")
            success = await self.coordinator.client.set_fridge_mode(mode_id)
            if not success:
                raise HomeAssistantError("Failed to set Hisense refrigerator work mode")

            self.coordinator.data["work_mode"] = option
            self.coordinator.data["work_mode_id"] = mode_id
            
            if option == "智能":
                self.coordinator.data["refrigerator_set_temperature"] = 5
                self.coordinator.data["freeze_set_temperature"] = -18
            elif option == "速冷":
                self.coordinator.data["refrigerator_set_temperature"] = 2
                self.coordinator.data["freeze_set_temperature"] = -16
        else:
            mode_id = VARIATION_MODE_MAP.get(option)
            if mode_id is None:
                raise HomeAssistantError(f"无效的变温模式选项: {option}")
            success = await self.coordinator.client.set_variation_mode(mode_id)
            if not success:
                raise HomeAssistantError(
                    "Failed to set Hisense refrigerator variation mode"
                )

            self.coordinator.data["variation_mode"] = option
            self.coordinator.data["variation_mode_id"] = mode_id
        
        self.coordinator.async_set_updated_data(self.coordinator.data)
        
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
