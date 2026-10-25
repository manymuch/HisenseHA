import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD
from .pyhisenseapi import HiSenseLogin

class HisenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        self._home_options = None
        self._access_token = None
        self._refresh_token = None
        self._customer_id = None
        self._device_info = None
        self._username = None
        self._password = None
        self._reauth_username = ""

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            hisense_login = HiSenseLogin(session=session)

            try:
                token_pair = await hisense_login.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except Exception:
                errors["base"] = "invalid_auth"
            else:
                if not token_pair:
                    errors["base"] = "invalid_auth"
                else:
                    access_token, refresh_token, customer_id = token_pair
                    try:
                        self._home_options = await hisense_login.get_home_select_options(
                            access_token, customer_id
                        )
                    except Exception:
                        errors["base"] = "cannot_connect"
                    else:
                        if self._home_options is None:
                            errors["base"] = "cannot_connect"
                        elif not self._home_options:
                            errors["base"] = "no_homes"
                        else:
                            self._access_token = access_token
                            self._refresh_token = refresh_token
                            self._customer_id = customer_id
                            self._username = user_input[CONF_USERNAME]
                            self._password = user_input[CONF_PASSWORD]
                            return await self.async_step_home()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
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
            try:
                self._device_info = await hisense_login.get_all_devices(
                    self._access_token,
                    home_id,
                    self._refresh_token,
                    self._customer_id,
                )
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                if self._device_info is None:
                    errors["base"] = "cannot_connect"
                elif not self._device_info:
                    errors["base"] = "no_devices"
                else:
                    return await self.async_step_device()

        return self.async_show_form(
            step_id="home",
            data_schema=vol.Schema(
                {vol.Required("home_id"): vol.In(self._home_options)}
            ),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        errors = {}

        if user_input is not None:
            device_ids = user_input["device_ids"]
            if not device_ids:
                errors["base"] = "no_devices"
            else:
                devices = [
                    self._device_info[device_id]
                    for device_id in device_ids
                ]
                return self.async_create_entry(
                    title="Hisense Smart Control",
                    data={
                        "devices": devices,
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                    },
                )

        device_id_to_label = {}
        for device_id, info in self._device_info.items():
            label = info.get("label", device_id)
            device_type = info.get("device_type", "")
            device_id_to_label[device_id] = f"{label} ({device_type})"

        data_schema = vol.Schema(
            {
                vol.Required("device_ids"): cv.multi_select(device_id_to_label),
            }
        )
        return self.async_show_form(
            step_id="device",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Collect credentials for an existing token-only entry."""
        self._reauth_username = entry_data.get(CONF_USERNAME, "")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Verify the account still contains the configured devices."""
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            login = HiSenseLogin(session)
            try:
                tokens = await login.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                if not tokens:
                    errors["base"] = "invalid_auth"
                else:
                    access_token, refresh_token, customer_id = tokens
                    entry = self._get_reauth_entry()
                    expected = {device["device_id"] for device in entry.data["devices"]}
                    home_ids = {
                        device.get("home_id")
                        for device in entry.data["devices"]
                        if device.get("home_id")
                    }
                    try:
                        visible = set()
                        for home_id in home_ids:
                            devices = await login.get_all_devices(
                                access_token, home_id, refresh_token, customer_id
                            )
                            if devices is None:
                                raise ValueError("AIHome device list failed")
                            visible.update(devices)
                    except Exception:
                        errors["base"] = "cannot_connect"
                    else:
                        if not home_ids or not expected.issubset(visible):
                            errors["base"] = "wrong_account"
                        else:
                            updated_devices = [
                                {
                                    **device,
                                    "access_token": access_token,
                                    "refresh_token": refresh_token,
                                    "customer_id": customer_id,
                                }
                                for device in entry.data["devices"]
                            ]
                            return self.async_update_reload_and_abort(
                                entry,
                                data_updates={
                                    "devices": updated_devices,
                                    CONF_USERNAME: user_input[CONF_USERNAME],
                                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                                },
                            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._reauth_username): str,
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )
