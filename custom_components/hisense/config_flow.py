# config_flow.py

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, CONF_WIFI_ID, CONF_DEVICE_ID, CONF_TOKEN


class HisenseACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Here you could add code to validate the input, such as attempting to connect to the AC
            # For simplicity, we'll assume the input is valid
            return self.async_create_entry(title="Hisense Smart Control", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_WIFI_ID): str,
                vol.Required(CONF_DEVICE_ID, ): str,
                vol.Required(CONF_TOKEN): str,
            }),
            description_placeholders={
                "wifi_id_hint": "WiFi ID here",
                "device_id_hint": "Device ID here",
                "token_hint": "Token here",
            },
            errors=errors,
        )
