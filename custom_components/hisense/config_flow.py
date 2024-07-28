import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD
from .pyhisenseapi import HiSenseLogin

class HisenseACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self._home_id_list = None
        self._access_token = None
        self._refresh_token = None

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            hisense_login = HiSenseLogin(session=session)

            try:
                access_token, refresh_token = await hisense_login.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                self._home_id_list = await hisense_login.get_home_id_list(access_token)
                self._access_token = access_token
                self._refresh_token = refresh_token
                return await self.async_step_home()
            except Exception: 
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "username_hint": "app login username",
                "password_hint": "app login password",
            },
            errors=errors,
        )

    async def async_step_home(self, user_input=None):
        errors = {}

        if user_input is not None:
            home_id = user_input["home_id"]
            session = async_get_clientsession(self.hass)
            hisense_login = HiSenseLogin(session=session)
            self._device_wifi_id_dict = await hisense_login.get_device_wifi_id_dict(
                self._access_token, home_id
            )

            return await self.async_step_device()

        return self.async_show_form(
            step_id="home",
            data_schema=vol.Schema(
                {vol.Required("home_id"): vol.In(self._home_id_list)}
            ),
            errors=errors,
        )
    
    async def async_step_device(self, user_input=None):
        if user_input is not None:
            device_ids = user_input["device_ids"]
            devices = [
                {"device_id": device_id,
                 "wifi_id": self._device_wifi_id_dict[device_id],
                 "refresh_token": self._refresh_token,
                 }
                for device_id in device_ids
            ]
            return self.async_create_entry(
                title="Hisense Smart Control", 
                data={"devices": devices}
            )

        data_schema = vol.Schema(
            {
                vol.Required("device_ids"): cv.multi_select(
                    list(self._device_wifi_id_dict.keys())
                ),
            }
        )
        return self.async_show_form(step_id="device", data_schema=data_schema)
