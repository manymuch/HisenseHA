from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HisenseEntity

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    entities = [HisenseACUpdateButton(coordinator) for coordinator in coordinators.values()]
    async_add_entities(entities)


class HisenseACUpdateButton(HisenseEntity, ButtonEntity):
    _attr_translation_key = "force_update"

    #: 手动恢复按钮在设备离线/断网时仍需可按，这是唯一的自救入口。
    _attr_available_offline = True

    def __init__(self, coordinator):
        super().__init__(coordinator, "force_update_button", "force_update")
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self):
        """Handle the button press."""
        _LOGGER.debug(f"Button pressed for entity: {self._attr_unique_id}")
        self.coordinator.async_start_refresh()
