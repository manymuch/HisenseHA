"""Home Assistant setup for the additional European backend."""
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .ayla_eu import AylaEU, AylaSplit, AylaAuthError, AylaError, PROFILE, profile_for
from .const import DOMAIN

PLATFORMS = ["climate", "switch", "button"]
_LOGGER = logging.getLogger(__name__)
_REAUTH_MESSAGE = "Sign in to HiSmart Life Europe again"


class EuropeanCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        self.client = client
        self.device_type = "空调"
        super().__init__(
            hass, _LOGGER, config_entry=entry, name="Hisense Europe", update_interval=None
        )

    async def _async_update_data(self):
        try:
            return await self.client.check_status()
        except AylaAuthError:
            raise ConfigEntryAuthFailed(_REAUTH_MESSAGE) from None
        except AylaError:
            raise UpdateFailed("European device state could not be read") from None

    async def async_command(self, setting, value):
        try:
            await self.client.command(setting, value)
        except AylaAuthError:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(_REAUTH_MESSAGE) from None
        except AylaError:
            raise HomeAssistantError("European command failed; refresh state before retrying") from None
        self.async_set_updated_data(self.client.get_status())


async def setup_entry(hass, entry):
    def save_tokens(tokens):
        hass.config_entries.async_update_entry(entry, data={**entry.data, "eu_tokens": tokens})

    api = AylaEU(async_get_clientsession(hass), entry.data.get("eu_tokens"), save_tokens)
    try:
        devices = {d.get("dsn"): d for d in await api.devices()}
    except AylaAuthError:
        raise ConfigEntryAuthFailed(_REAUTH_MESSAGE) from None
    except AylaError:
        raise ConfigEntryNotReady("European device list could not be read") from None

    coordinators = {}
    skipped_devices = 0
    for info in entry.data["devices"]:
        device_id = info["device_id"]
        device = devices.get(device_id)
        if device is None or profile_for(device) != PROFILE:
            skipped_devices += 1
            continue
        client = AylaSplit(api, device_id, info.get("label") or "Hisense EU AC")
        coordinator = EuropeanCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()
        coordinators[device_id] = coordinator

    if not coordinators:
        raise ConfigEntryNotReady("No configured European Smart-1-110 devices were found")
    if skipped_devices:
        _LOGGER.warning(
            "Skipped %d configured European AC(s) missing from the account or using an unsupported profile",
            skipped_devices,
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
