from homeassistant import config_entries, core
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN
from .pyhisenseapi import HiSenseLogin, HiSenseAC


async def async_setup(hass: core.HomeAssistant, config: dict):
    # Initialize integration data structure
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    # Setup the API client for a device
    session = async_get_clientsession(hass)
    hisense_login = HiSenseLogin(
        session=session
    )

    access_token, refresh_token = await hisense_login.login(entry.data["username"], entry.data["password"])
    home_id_list = await hisense_login.get_home_id_list(access_token)
    # TODO let the user to select home_id
    home_id = home_id_list[0]
    device_id_list, wifi_id_list = await hisense_login.get_device_id_list(access_token, home_id)
    # TODO let the user to select device
    device_id = device_id_list[0]
    wifi_id = wifi_id_list[0]
    
    hass.data[DOMAIN][entry.entry_id] = HiSenseAC(
        wifi_id=wifi_id,
        device_id=device_id,
        refresh_token=refresh_token,
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
