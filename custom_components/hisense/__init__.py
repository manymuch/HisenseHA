from homeassistant import config_entries, core
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN
from .pyhisenseapi import HiSenseAC


async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    
    session = async_get_clientsession(hass)
    # Setup devices based on the selected devices from the config flow
    for device_info in entry.data["devices"]:
        device_id = device_info["device_id"]
        wifi_id = device_info["wifi_id"]
        refresh_token = device_info["refresh_token"]
        hass.data[DOMAIN][entry.entry_id][device_id] = HiSenseAC(
            wifi_id=wifi_id,
            device_id=device_id,
            refresh_token=refresh_token,
            session=session
        )

        for platform in ("climate", "switch", "button"):
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    return True

async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    return all(
        await hass.config_entries.async_forward_entry_unload(entry, platform)
        for platform in ("climate", "switch", "button")
    )
