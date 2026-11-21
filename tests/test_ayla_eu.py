"""Offline contract tests. Uses synthetic data; no account or device access."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ayla_eu", ROOT / "custom_components/hisense/ayla_eu.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


def props(packed=(23 << 17) | (2 << 9) | (6 << 1)):
    return {"t_control_value": {"name": "t_control_value", "base_type": "integer", "direction": "input", "read_only": False, "value": packed},
            "t_power": {"name": "t_power", "base_type": "boolean", "direction": "input", "read_only": False, "value": 1},
            "t_backlight": {"name": "t_backlight", "base_type": "boolean", "direction": "input", "read_only": False, "value": 0},
            "f_temp_in": {"name": "f_temp_in", "base_type": "decimal", "direction": "output", "read_only": True, "value": 24.5}}


class Response:
    def __init__(self, status, payload):
        self.status, self.payload = status, payload
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return Response(*self.responses.pop(0))


def auth(access="access", refresh="refresh"):
    return {"access_token": access, "refresh_token": refresh, "expires_in": 3600}


def tokens():
    return {"access_token": "old-access", "refresh_token": "old-refresh", "expires_at": time.time() + 1000}


class CodecTests(unittest.TestCase):
    def test_profile_requires_exact_variant(self):
        self.assertEqual(api.profile_for({"oem_model": "Smart-1-110-build"}), api.PROFILE)
        self.assertNotEqual(api.profile_for({"oem_model": "Smart-1-111-build"}), api.PROFILE)
        self.assertIsNone(api.profile_for({}))

    def test_fields_preserve_other_bits_and_set_enable_flag(self):
        for field, (start, width) in api.FIELDS.items():
            for original in (0, 0xAAAAAAAA, 0xFFFFFFFF, 0x80000000, 0x12345678):
                for value in range(1 << width):
                    encoded = api.encode_bits(original, field, value) & 0xFFFFFFFF
                    mask = ((1 << (width + 1)) - 1) << (start - 1)
                    self.assertEqual(encoded & ~mask, original & ~mask)
                    self.assertEqual(api.decode_bits(encoded, field), value)
                    self.assertTrue(encoded & (1 << (start - 1)))

    def test_independent_known_command_words(self):
        self.assertEqual(api.encode_bits(0, "fan", 6), 13)
        self.assertEqual(api.encode_bits(0, "mode", 1), 768)
        self.assertEqual(api.encode_bits(0, "temperature", 23), 3080192)
        self.assertEqual(api.encode_bits(-2147483648, "fan", 8), -2147483631)

    def test_invalid_words_and_ranges(self):
        for word in (None, True, 1.5, "23", 1 << 32):
            with self.assertRaises(api.AylaError):
                api.decode_bits(word, "fan")
        for value in (-1, 16, True):
            with self.assertRaises(api.AylaError):
                api.encode_bits(0, "fan", value)

    def test_celsius_and_display_inversion(self):
        state = api.decode_state(props())
        self.assertEqual(state["fan_mode"], "low")
        self.assertEqual(state["hvac_mode"], "cool")
        self.assertEqual(state["desired_temperature"], 23)
        self.assertEqual(state["indoor_temperature"], 24.5)
        self.assertTrue(state["screen_on"])

    def test_fahrenheit_target_and_room_marker(self):
        properties = props(0x80000000 | (77 << 17))
        properties["f_temp_in"]["value"] = 177
        state = api.decode_state(properties)
        self.assertEqual(state["desired_temperature"], 25)
        self.assertEqual(state["indoor_temperature"], 25)

    def test_missing_temperature_is_unknown(self):
        properties = props(0)
        properties["f_temp_in"]["value"] = None
        state = api.decode_state(properties)
        self.assertIsNone(state["desired_temperature"])
        self.assertIsNone(state["indoor_temperature"])


class AuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_shape_and_token_callback(self):
        session = Session([(200, auth())])
        saved = []
        client = api.AylaEU(session, on_tokens=saved.append)
        await client.login("fake@example.invalid", "FAKE_PASSWORD")
        method, url, options = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, api.USER_URL + "users/sign_in.json")
        self.assertEqual(options["json"]["user"]["application"], api.APPLICATION)
        self.assertNotIn("Authorization", options["headers"])
        self.assertFalse(options["allow_redirects"])
        self.assertEqual(saved[-1]["refresh_token"], "refresh")
        self.assertNotIn("FAKE_PASSWORD", json.dumps(saved))

    async def test_refresh_rotates_and_persists(self):
        session = Session([(200, auth("new", "rotated"))])
        saved = []
        client = api.AylaEU(session, tokens(), saved.append)
        await client.refresh(force=True)
        self.assertEqual(session.calls[0][1], api.USER_URL + "users/refresh_token.json")
        self.assertEqual(session.calls[0][2]["json"], {"user": {"refresh_token": "old-refresh"}})
        self.assertEqual(session.calls[0][2]["headers"]["Authorization"], "auth_token old-access")
        self.assertEqual(saved[-1]["refresh_token"], "rotated")

    async def test_valid_token_does_not_refresh(self):
        client = api.AylaEU(Session([]), tokens())
        await client.refresh()
        self.assertEqual(client.session.calls, [])

    async def test_rejection_refreshes_once(self):
        session = Session([(401, {"secret": "DO_NOT_PRINT"}), (200, auth()), (200, [])])
        client = api.AylaEU(session, tokens())
        self.assertEqual(await client.devices(), [])
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[-1][2]["headers"]["Authorization"], "auth_token access")

    async def test_failed_refresh_requires_reauth_without_leak(self):
        client = api.AylaEU(Session([(401, {"secret": "DO_NOT_PRINT"})]), tokens())
        with self.assertRaises(api.AylaAuthError) as error:
            await client.refresh(force=True)
        self.assertNotIn("DO_NOT_PRINT", str(error.exception))

    async def test_redirect_does_not_leak_or_follow(self):
        session = Session([(302, {"url": "https://example.invalid/token"})])
        client = api.AylaEU(session, tokens())
        with self.assertRaises(api.AylaError):
            await client.devices()
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(session.calls[0][2]["allow_redirects"])

    async def test_bad_token_contract(self):
        for payload in ({}, {**auth(), "expires_in": "NaN"}, {**auth(), "expires_in": -1}):
            client = api.AylaEU(Session([(200, payload)]))
            with self.assertRaises(api.AylaError):
                await client.login("fake", "fake")


class DeviceTests(unittest.IsolatedAsyncioTestCase):
    async def run_command(self, setting, value, properties=None):
        properties = properties or props()
        wrappers = [{"property": p} for p in properties.values()]
        session = Session([(200, wrappers), (201, {"datapoint": {"value": 0}}), (200, wrappers)])
        client = api.AylaSplit(api.AylaEU(session, tokens()), "fake/dsn")
        await client.command(setting, value)
        return session, client

    async def test_reads_fresh_state_then_writes_correct_endpoint(self):
        session, _ = await self.run_command("fan", "high")
        self.assertEqual([c[0] for c in session.calls], ["GET", "POST", "GET"])
        self.assertEqual(session.calls[1][1], api.DEVICE_URL + "apiv1/dsns/fake%2Fdsn/properties/t_control_value/datapoints.json")
        value = session.calls[1][2]["json"]["datapoint"]["value"]
        self.assertEqual(api.decode_bits(value, "fan"), 8)
        self.assertEqual(api.decode_bits(value, "temperature"), 23)

    async def test_power_and_display_use_independent_properties(self):
        for setting, value, prop, encoded in (("power", True, "t_power", 1), ("power", False, "t_power", 0),
                ("screen", True, "t_backlight", 0), ("screen", False, "t_backlight", 1)):
            session, _ = await self.run_command(setting, value)
            self.assertIn("/" + prop + "/", session.calls[1][1])
            self.assertEqual(session.calls[1][2]["json"], {"datapoint": {"value": encoded}})

    async def test_fahrenheit_command_keeps_unit(self):
        session, _ = await self.run_command("temperature", 25, props(0x80000000 | (75 << 17)))
        encoded = session.calls[1][2]["json"]["datapoint"]["value"]
        self.assertLess(encoded, 0)
        self.assertEqual(api.decode_bits(encoded, "temperature"), 77)

    async def test_refuses_read_only_property(self):
        properties = props()
        properties["t_control_value"]["read_only"] = True
        session = Session([(200, [{"property": p} for p in properties.values()])])
        client = api.AylaSplit(api.AylaEU(session, tokens()), "fake")
        with self.assertRaises(api.AylaError):
            await client.command("temperature", 24)
        self.assertEqual([c[0] for c in session.calls], ["GET"])

    async def test_rejects_unvalidated_or_invalid_commands(self):
        for setting, value in (("fan", "diffuse"), ("mode", "unknown"), ("temperature", 33),
                ("temperature", float("nan")), ("temperature", 22.5), ("sleep", 1), ("power", "yes")):
            properties = props()
            session = Session([(200, [{"property": p} for p in properties.values()])])
            client = api.AylaSplit(api.AylaEU(session, tokens()), "fake")
            with self.assertRaises(api.AylaError):
                await client.command(setting, value)
            self.assertEqual(len(session.calls), 1)

    async def test_init_is_read_only(self):
        properties = props()
        session = Session([(200, [{"property": p} for p in properties.values()])])
        client = api.AylaSplit(api.AylaEU(session, tokens()), "fake")
        await client.check_status()
        self.assertEqual([c[0] for c in session.calls], ["GET"])


if __name__ == "__main__":
    unittest.main()
