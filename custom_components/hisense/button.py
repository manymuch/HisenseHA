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

    tv_coordinators = [c for c in coordinators.values() if getattr(c, "device_type", None) == "电视"]
    tv_buttons = [
        HisenseTVKeyButton(c, name, code, icon)
        for c in tv_coordinators
        for name, code, icon in TV_KEY_BUTTONS
    ]
    if tv_buttons:
        async_add_entities(tv_buttons)


TV_KEY_BUTTONS = (
    ("power", "KEY_POWER", "mdi:power"),
    ("home", "KEY_HOME", "mdi:home"),
    ("back", "KEY_RETURNS", "mdi:keyboard-backspace"),
    ("menu", "KEY_MENU", "mdi:menu"),
    ("ok", "KEY_OK", "mdi:checkbox-marked-circle-outline"),
    ("up", "KEY_UP", "mdi:arrow-up-bold"),
    ("down", "KEY_DOWN", "mdi:arrow-down-bold"),
    ("left", "KEY_LEFT", "mdi:arrow-left-bold"),
    ("right", "KEY_RIGHT", "mdi:arrow-right-bold"),
    ("volume_up", "KEY_VOLUMEUP", "mdi:volume-plus"),
    ("volume_down", "KEY_VOLUMEDOWN", "mdi:volume-minus"),
    ("mute", "KEY_MUTE", "mdi:volume-mute"),
    ("control_center", "KEY_CONTROL_CENTER", "mdi:tune-vertical"),
)


class HisenseTVKeyButton(HisenseEntity, ButtonEntity):
    def __init__(self, coordinator, key_name: str, key_code: str, icon: str):
        super().__init__(coordinator, f"tv_key_{key_name}", f"tv_key_{key_name}", icon)
        self._key_code = key_code
        self._attr_translation_key = f"tv_key_{key_name}"

    async def async_press(self):
        await self.client.send_key(self._key_code)
        self.coordinator.async_update_from_client()


class HisenseACUpdateButton(HisenseEntity, ButtonEntity):
    _attr_translation_key = "force_update"

    #: Keep the refrigerator refresh button usable while the device is offline.
    _attr_available_offline = True

    def __init__(self, coordinator):
        super().__init__(coordinator, "force_update_button", "force_update")
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self):
        """Handle the button press."""
        _LOGGER.debug(f"Button pressed for entity: {self._attr_unique_id}")
        self.coordinator.async_start_refresh()
