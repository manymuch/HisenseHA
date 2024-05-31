from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from homeassistant.const import EntityCategory
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    api = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HisenseACUpdateButton(api)], True)
    async_add_entities([HisenseACRefreshTokenButton(api)], True)


class HisenseACUpdateButton(ButtonEntity):
    def __init__(self, api):
        self._api = api
        self._attr_name = f"Force update button"
        self._attr_unique_id = f"{api.device_id}_force_update_button"
        self._attr_icon = "mdi:refresh"

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._api.device_id)},
            "name": "Hisense AC",
            "manufacturer": "Hisense",
        }

    @property
    def name(self):
        return "Force Update"

    async def async_press(self):
        """Handle the button press."""
        _LOGGER.debug(f"Button pressed for entity: {self._attr_unique_id}")
        await self._api.check_status()
        # Ensure the climate entity is updated after status check
        climate_entity = self.hass.data[DOMAIN].get(self._api.device_id)
        if climate_entity:
            await climate_entity.async_update()
            climate_entity.async_write_ha_state()


class HisenseACRefreshTokenButton(ButtonEntity):
    def __init__(self, api):
        self._api = api
        self._attr_name = f"Refresh token"
        self._attr_unique_id = f"{api.device_id}_refresh_token"
        self._attr_icon = "mdi:refresh"

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._api.device_id)},
            "name": "Hisense AC",
            "manufacturer": "Hisense",
        }

    @property
    def name(self):
        return "Refresh token"

    async def async_press(self):
        """Handle the button press."""
        _LOGGER.debug(f"Button pressed for entity: {self._attr_unique_id}")
        await self._api.refresh()
