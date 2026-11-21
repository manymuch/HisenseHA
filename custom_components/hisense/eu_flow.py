"""Additional European setup and reauthentication steps."""
import hashlib

import voluptuous as vol
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .ayla_eu import AylaEU, AylaAuthError, AylaError, PROFILE, profile_for


def login_schema(region=True):
    fields = {}
    if region:
        fields[vol.Required("region", default="EU")] = vol.In({"CN": "China (HisenseHA)", "EU": "Europe (HiSmart Life / Ayla)"})
    fields[vol.Required("username")] = str
    fields[vol.Required("password")] = selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))
    return vol.Schema(fields)


class EuropeanFlow:
    async def async_step_eu_user(self, user_input):
        errors = {}
        api = AylaEU(async_get_clientsession(self.hass))
        try:
            await api.login(user_input["username"].strip(), user_input["password"])
            devices = await api.devices()
        except AylaAuthError:
            errors["base"] = "invalid_auth"
        except AylaError:
            errors["base"] = "cannot_connect"
        else:
            supported = [d for d in devices if profile_for(d) == PROFILE and isinstance(d.get("dsn"), str) and d["dsn"]]
            if not supported:
                errors["base"] = "eu_unsupported_profile"
            else:
                email_hash = hashlib.sha256(user_input["username"].strip().casefold().encode()).hexdigest()
                await self.async_set_unique_id("eu:" + email_hash)
                self._abort_if_unique_id_configured()
                self._eu_tokens = dict(api.tokens)
                self._eu_devices = {d["dsn"]: {
                    "device_id": d["dsn"], "profile": PROFILE,
                    "label": d.get("product_name") or "Hisense EU AC",
                } for d in supported}
                return await self.async_step_eu_device()
        return self.async_show_form(step_id="user", data_schema=login_schema(), errors=errors)

    async def async_step_eu_device(self, user_input=None):
        errors = {}
        if user_input is not None:
            ids = user_input.get("device_ids", [])
            if not ids or any(d not in self._eu_devices for d in ids):
                errors["base"] = "no_devices"
            else:
                return self.async_create_entry(title="Hisense Europe", data={
                    "region": "EU", "eu_tokens": self._eu_tokens,
                    "devices": [self._eu_devices[d] for d in ids]})
        labels = {d: f"{info['label']} ({index})" for index, (d, info) in enumerate(self._eu_devices.items(), 1)}
        return self.async_show_form(step_id="eu_device", data_schema=vol.Schema({
            vol.Required("device_ids"): cv.multi_select(labels)}), errors=errors)

    async def async_step_reauth(self, entry_data):
        if entry_data.get("region") != "EU":
            return self.async_abort(reason="eu_reauth_only")
        self._eu_reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_eu_reauth()

    async def async_step_eu_reauth(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = AylaEU(async_get_clientsession(self.hass))
            try:
                await api.login(user_input["username"].strip(), user_input["password"])
                devices = {d.get("dsn") for d in await api.devices() if profile_for(d) == PROFILE}
                expected = {d["device_id"] for d in self._eu_reauth_entry.data["devices"]}
                if not expected.issubset(devices):
                    errors["base"] = "eu_account_mismatch"
                else:
                    return self.async_update_reload_and_abort(self._eu_reauth_entry,
                        data_updates={"eu_tokens": dict(api.tokens)})
            except AylaAuthError:
                errors["base"] = "invalid_auth"
            except AylaError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="eu_reauth", data_schema=login_schema(False), errors=errors)
