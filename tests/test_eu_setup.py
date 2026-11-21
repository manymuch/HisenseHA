"""Setup contracts with lightweight HA substitutes, not a real HA runtime."""
import importlib.util
import sys
from pathlib import Path
import types
import unittest
from unittest.mock import AsyncMock, patch

from test_ayla_eu import Session, auth, tokens, props

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components/hisense"


def module(name, **attrs):
    return types.ModuleType(name, **{}) if not attrs else _module(name, attrs)


def _module(name, attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class AuthFailed(Exception):
    pass


class NotReady(Exception):
    pass


class Coordinator:
    def __init__(self, hass, *args, **kwargs):
        self.hass = hass
        self.data = None
    async def async_config_entry_first_refresh(self):
        self.data = await self._async_update_data()
    def async_set_updated_data(self, data):
        self.data = data


class Flow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    def __init__(self, hass):
        self.hass = hass
    async def async_set_unique_id(self, uid):
        self.unique_id = uid
    def _abort_if_unique_id_configured(self):
        pass
    def async_show_form(self, **kw):
        return {"type": "form", **kw}
    def async_create_entry(self, **kw):
        return {"type": "create_entry", **kw}
    def async_update_reload_and_abort(self, entry, data_updates):
        entry.data = {**entry.data, **data_updates}
        return {"type": "abort", "reason": "reauth_successful"}


class SetupTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cv = module("homeassistant.helpers.config_validation", multi_select=lambda x: x)
        selector = module("homeassistant.helpers.selector", TextSelector=lambda x: x,
            TextSelectorConfig=lambda **kw: kw, TextSelectorType=types.SimpleNamespace(PASSWORD="password"))
        stubs = {
            "voluptuous": module("voluptuous", Schema=lambda x: x, Required=lambda x, **kw: x, In=lambda x: x),
            "homeassistant": module("homeassistant"),
            "homeassistant.config_entries": module("homeassistant.config_entries", ConfigFlow=Flow, CONN_CLASS_CLOUD_POLL="cloud_poll"),
            "homeassistant.helpers": module("homeassistant.helpers", config_validation=cv, selector=selector),
            "homeassistant.helpers.config_validation": cv,
            "homeassistant.helpers.selector": selector,
            "homeassistant.helpers.aiohttp_client": module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda h: h.session),
            "homeassistant.helpers.update_coordinator": module("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=Coordinator, UpdateFailed=NotReady),
            "homeassistant.exceptions": module("homeassistant.exceptions", ConfigEntryAuthFailed=AuthFailed, ConfigEntryNotReady=NotReady),
            "eu_test_pkg": module("eu_test_pkg", __path__=[str(COMPONENT)]),
            "eu_test_pkg.const": module("eu_test_pkg.const", DOMAIN="hisense", CONF_USERNAME="username", CONF_PASSWORD="password"),
            "eu_test_pkg.pyhisenseapi": module("eu_test_pkg.pyhisenseapi", HiSenseLogin=None),
        }
        cls.patcher = patch.dict(sys.modules, stubs)
        cls.patcher.start()
        import importlib
        cls.flow_module = importlib.import_module("eu_test_pkg.eu_flow")
        cls.setup_module = importlib.import_module("eu_test_pkg.eu")
        cls.config_flow = importlib.import_module("eu_test_pkg.config_flow")
        cls.Harness = type("Harness", (Flow, cls.flow_module.EuropeanFlow), {})

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def hass(self, session):
        def update(entry, data):
            entry.data = data
        entries = types.SimpleNamespace(async_update_entry=update, async_forward_entry_setups=AsyncMock())
        return types.SimpleNamespace(session=session, data={}, config_entries=entries)

    async def test_eu_setup_skips_home_step_and_never_saves_password(self):
        session = Session([(200, auth()), (200, [{"device": {"dsn": "FAKE_DSN", "oem_model": "Smart-1-110-fake"}},
            {"device": {"dsn": "other", "oem_model": "Smart-1-111-fake"}}])])
        flow = self.Harness(self.hass(session))
        result = await flow.async_step_eu_user({"username": "fake@example.invalid", "password": "PRIVATE_PASSWORD"})
        self.assertEqual(result["step_id"], "eu_device")
        self.assertEqual(set(flow._eu_devices), {"FAKE_DSN"})
        result = await flow.async_step_eu_device({"device_ids": ["FAKE_DSN"]})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["region"], "EU")
        self.assertNotIn("password", str(result["data"]))
        self.assertNotIn("PRIVATE_PASSWORD", str(flow.__dict__))
        self.assertNotIn("fake@example.invalid", str(result["data"]))

    async def test_unsupported_variant_is_not_created(self):
        session = Session([(200, auth()), (200, [{"device": {"dsn": "fake", "oem_model": "Smart-1-111-fake"}}])])
        flow = self.Harness(self.hass(session))
        result = await flow.async_step_eu_user({"username": "fake", "password": "fake"})
        self.assertEqual(result["errors"]["base"], "eu_unsupported_profile")

    async def test_invalid_device_selection_does_not_create_entry(self):
        flow = self.Harness(self.hass(Session([])))
        flow._eu_devices = {"fake": {"label": "AC"}}
        result = await flow.async_step_eu_device({"device_ids": ["unknown"]})
        self.assertEqual(result["errors"]["base"], "no_devices")

    async def test_setup_with_valid_tokens_only_reads_cloud(self):
        wrappers = [{"property": p} for p in props().values()]
        session = Session([(200, [{"device": {"dsn": "fake", "oem_model": "Smart-1-110-build"}}]), (200, wrappers)])
        hass = self.hass(session)
        entry = types.SimpleNamespace(entry_id="entry", data={"region": "EU", "eu_tokens": tokens(), "devices": [{"device_id": "fake", "label": "AC"}]})
        self.assertTrue(await self.setup_module.setup_entry(hass, entry))
        self.assertEqual([c[0] for c in session.calls], ["GET", "GET"])
        hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(entry, ["climate", "switch", "button"])
        self.assertEqual(hass.data["hisense"]["entry"]["fake"].data["fan_mode"], "low")

    async def test_rotated_tokens_are_saved_to_entry(self):
        wrappers = [{"property": p} for p in props().values()]
        session = Session([(200, auth("new", "rotated")),
            (200, [{"device": {"dsn": "fake", "oem_model": "Smart-1-110-build"}}]), (200, wrappers)])
        hass = self.hass(session)
        entry = types.SimpleNamespace(entry_id="entry", data={"region": "EU", "eu_tokens": {**tokens(), "expires_at": 0}, "devices": [{"device_id": "fake"}]})
        await self.setup_module.setup_entry(hass, entry)
        self.assertEqual(entry.data["eu_tokens"]["refresh_token"], "rotated")
        self.assertEqual(len(entry.data["devices"]), 1)

    async def test_setup_auth_failure_requests_reauth(self):
        hass = self.hass(Session([(401, {})]))
        entry = types.SimpleNamespace(data={"eu_tokens": {**tokens(), "expires_at": 0}})
        with self.assertRaises(AuthFailed):
            await self.setup_module.setup_entry(hass, entry)

    async def test_reauth_rejects_other_account(self):
        session = Session([(200, auth()), (200, [{"device": {"dsn": "other", "oem_model": "Smart-1-110-build"}}])])
        flow = self.Harness(self.hass(session))
        flow._eu_reauth_entry = types.SimpleNamespace(data={"devices": [{"device_id": "expected"}]})
        result = await flow.async_step_eu_reauth({"username": "fake", "password": "fake"})
        self.assertEqual(result["errors"]["base"], "eu_account_mismatch")

    async def test_reauth_updates_tokens_for_same_devices(self):
        session = Session([(200, auth("new", "rotated")), (200, [{"device": {"dsn": "expected", "oem_model": "Smart-1-110-build"}}])])
        flow = self.Harness(self.hass(session))
        flow._eu_reauth_entry = types.SimpleNamespace(data={"region": "EU", "devices": [{"device_id": "expected"}]})
        result = await flow.async_step_eu_reauth({"username": "fake", "password": "fake"})
        self.assertEqual(result["reason"], "reauth_successful")
        self.assertEqual(flow._eu_reauth_entry.data["eu_tokens"]["refresh_token"], "rotated")
        self.assertNotIn("password", flow._eu_reauth_entry.data)

    async def test_existing_account_input_uses_original_home_selection(self):
        for region in (None, "CN"):
            login = types.SimpleNamespace(login=AsyncMock(return_value=("access", "refresh", "customer")),
                get_home_select_options=AsyncMock(return_value={"home": "Home"}))
            flow = self.config_flow.HisenseConfigFlow()
            flow.hass = self.hass(Session([]))
            data = {"username": "fake", "password": "fake"}
            if region:
                data["region"] = region
            with patch.object(self.config_flow, "HiSenseLogin", return_value=login):
                result = await flow.async_step_user(data)
            self.assertEqual(result["step_id"], "home")
            login.get_home_select_options.assert_awaited_once_with("access", "customer")

    async def test_european_input_bypasses_original_login(self):
        session = Session([(200, auth()), (200, [{"device": {"dsn": "fake", "oem_model": "Smart-1-110-build"}}])])
        flow = self.config_flow.HisenseConfigFlow()
        flow.hass = self.hass(session)
        with patch.object(self.config_flow, "HiSenseLogin", side_effect=AssertionError("Wrong backend")):
            result = await flow.async_step_user({"region": "EU", "username": "fake", "password": "fake"})
        self.assertEqual(result["step_id"], "eu_device")
        self.assertIsNone(flow._password)

    async def test_european_reauth_uses_existing_entry(self):
        entry = types.SimpleNamespace(data={"region": "EU", "devices": [{"device_id": "fake"}]})
        flow = self.config_flow.HisenseConfigFlow()
        flow.hass = self.hass(Session([]))
        flow.hass.config_entries.async_get_entry = lambda entry_id: entry
        flow.context = {"entry_id": "existing"}
        result = await flow.async_step_reauth(entry.data)
        self.assertEqual(result["step_id"], "eu_reauth")
        self.assertIs(flow._eu_reauth_entry, entry)


if __name__ == "__main__":
    unittest.main()
