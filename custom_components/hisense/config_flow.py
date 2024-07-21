import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD


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
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD, ): str,
            }),
            description_placeholders={
                "username_hint": "app login username",
                "password_hint": "app login password",
            },
            errors=errors,
        )
    