from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]
    entities = [AcScreenSwitch(api[device_id]) for device_id in api]
    async_add_entities(entities, True)
    entities = [AuxHeatSwitch(api[device_id]) for device_id in api]
    async_add_entities(entities, True)


class AcScreenSwitch(SwitchEntity):
    def __init__(self, api):
        self._api = api
        self._attr_unique_id = f"{api.device_id}_screen"
        self._is_on = True
        self._attr_icon = "mdi:clock-digital"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._api.device_id)},
            "name": "Hisense AC",
            "manufacturer": "Hisense",
        }

    @property
    def name(self):
        return "Screen Panel"

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self):
        _LOGGER.debug(f"Turning on screen for {self._attr_unique_id}")
        await self._api.send_logic_command(41, 1)
        self._is_on = True
        await self.async_update()
        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self):
        _LOGGER.debug(f"Turning off screen for {self._attr_unique_id}")
        await self._api.send_logic_command(41, 0)
        self._is_on = False
        await self.async_update()
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        status = self._api.get_status()
        self._is_on = status.get("screen_on", True)


class AuxHeatSwitch(SwitchEntity):
    def __init__(self, api):
        self._api = api
        self._attr_unique_id = f"{api.device_id}_aux_heat"
        self._is_on = False
        self._attr_icon = "mdi:heating-coil"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._api.device_id)},
            "name": "Hisense AC",
            "manufacturer": "Hisense",
        }

    @property
    def name(self):
        return "Aux Heat"

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self):
        await self._api.send_logic_command(28, 1)
        self._is_on = True
        await self.async_update()
        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self):
        await self._api.send_logic_command(28, 0)
        self._is_on = False
        await self.async_update()
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        status = self._api.get_status()
        self._is_on = status.get("aux_heat", False)
