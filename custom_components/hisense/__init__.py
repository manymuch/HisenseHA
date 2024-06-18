from homeassistant import config_entries, core
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .pyhisenseapi import HiSenseApi  # Import your API class


async def async_setup(hass: core.HomeAssistant, config: dict):
    # Initialize integration data structure
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    # Setup the API client for a device
    session = async_get_clientsession(hass)
    hass.data[DOMAIN][entry.entry_id] = HiSenseApi(
        wifi_id=entry.data["wifi_id"],
        device_id=entry.data["device_id"],
        refresh_token=entry.data["token"],
        session=session
    )
    # Forward the setup to the climate platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "button"))
    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    # Unload both climate and switch config entries
    unload_climate = await hass.config_entries.async_forward_entry_unload(entry, "climate")
    unload_switch = await hass.config_entries.async_forward_entry_unload(entry, "switch")
    unload_button = await hass.config_entries.async_forward_entry_unload(entry, "button")
    if unload_climate and unload_switch and unload_button:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_climate and unload_switch and unload_button
