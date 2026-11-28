"""European Ayla API and Smart-1-110 codec, traced from HiSmart Life 1.0.17.

This module never logs request bodies, account data, identifiers or tokens.
"""
from __future__ import annotations

import asyncio
import math
import time
from urllib.parse import quote

USER_URL = "https://user-field-eu.aylanetworks.com/"
DEVICE_URL = "https://ads-eu.aylanetworks.com/"
# Application-wide identity shipped in the official EU app; not user credentials.
APPLICATION = {"app_id": "Hisense-mw-id", "app_secret": "Hisense-wO1LLP8rWPr2cIeqvFaI-0m0z60"}
PROFILE = "Smart-1-110"
FANS = {"auto": 0, "quiet": 1, "super_low": 5, "low": 6, "medium": 7, "high": 8, "super_high": 9}
MODES = {"fan_only": 0, "heat": 1, "cool": 2, "dry": 3, "auto": 4}
FIELDS = {"fan": (1, 4), "power": (6, 1), "mode": (9, 3), "temperature": (17, 7)}


class AylaError(Exception):
    """Sanitized API error."""


class AylaAuthError(AylaError):
    """Local reauthentication is required."""


def profile_for(device):
    model = device.get("oem_model")
    return model.rsplit("-", 1)[0] if isinstance(model, str) else None


def word(value):
    if type(value) is not int or not -(1 << 31) <= value < (1 << 32):
        raise AylaError("Invalid packed control state")
    return value & 0xFFFFFFFF


def decode_bits(value, field):
    start, width = FIELDS[field]
    return (word(value) >> start) & ((1 << width) - 1)


def encode_bits(value, field, setting):
    """Reproduce ConfigKt.writeBitWithEnableBit, preserving unrelated bits."""
    start, width = FIELDS[field]
    if type(setting) is not int or not 0 <= setting < (1 << width):
        raise AylaError("Control value is out of range")
    mask = ((1 << (width + 1)) - 1) << (start - 1)
    encoded = (word(value) & ~mask) | (((setting << 1) | 1) << (start - 1))
    return encoded if encoded < (1 << 31) else encoded - (1 << 32)


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def decode_state(properties):
    packed = word(properties["t_control_value"]["value"])
    raw_target = decode_bits(packed, "temperature")
    fahrenheit = bool(packed & (1 << 31))
    target = (raw_target - 32) * 5 / 9 if fahrenheit else raw_target
    # App JS getTempIn: values >100 carry Fahrenheit with a +100 marker.
    indoor = properties.get("f_temp_in", {}).get("value")
    if numeric(indoor):
        indoor = (indoor - 132) * 5 / 9 if indoor > 100 else indoor
    else:
        indoor = None
    mode = decode_bits(packed, "mode")
    fan = decode_bits(packed, "fan")
    power = properties.get("t_power", {}).get("value")
    if type(power) not in (bool, int) or power not in (0, 1):
        raise AylaError("Invalid power state")
    screen = properties.get("t_backlight", {}).get("value")
    return {"power_on": bool(power),
            "hvac_mode": next((k for k, v in MODES.items() if v == mode), None),
            "fan_mode": next((k for k, v in FANS.items() if v == fan), None),
            "desired_temperature": round(target, 1) if 15.5 <= target <= 32.5 else None,
            "indoor_temperature": round(indoor, 1) if indoor is not None else None,
            "screen_on": not bool(screen) if type(screen) in (bool, int) and screen in (0, 1) else None}


class AylaEU:
    def __init__(self, session, tokens=None, on_tokens=None):
        self.session = session
        self.tokens = dict(tokens or {})
        self.on_tokens = on_tokens
        self._refresh_lock = asyncio.Lock()

    async def _raw(self, method, url, *, body=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "auth_token " + token
        try:
            async with self.session.request(method, url, headers=headers, json=body,
                                            allow_redirects=False, timeout=30) as response:
                if response.status in (401, 403):
                    raise AylaAuthError("European login expired or was rejected")
                if not 200 <= response.status < 300:
                    raise AylaError(f"European cloud returned HTTP {response.status}")
                return await response.json()
        except AylaError:
            raise
        except Exception:
            raise AylaError("European cloud request or response failed") from None

    def _accept_tokens(self, data):
        if not isinstance(data, dict):
            raise AylaError("Unexpected European authorization response")
        access = data.get("access_token")
        refresh = data.get("refresh_token") or self.tokens.get("refresh_token")
        if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
            raise AylaError("Incomplete European authorization response")
        try:
            lifetime = float(data["expires_in"])
            if not math.isfinite(lifetime) or lifetime <= 0:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise AylaError("Invalid European authorization lifetime") from None
        self.tokens = {"access_token": access, "refresh_token": refresh,
                       "expires_at": time.time() + lifetime}
        if self.on_tokens:
            self.on_tokens(dict(self.tokens))

    async def login(self, email, password):
        self._accept_tokens(await self._raw("POST", USER_URL + "users/sign_in.json",
            body={"user": {"email": email, "password": password, "application": APPLICATION}}))

    async def refresh(self, force=False, rejected=None):
        async with self._refresh_lock:
            if rejected and self.tokens.get("access_token") != rejected:
                return
            if not force and self.tokens.get("access_token") and self.tokens.get("expires_at", 0) > time.time() + 60:
                return
            token = self.tokens.get("refresh_token")
            if not token:
                raise AylaAuthError("European login required")
            self._accept_tokens(await self._raw("POST", USER_URL + "users/refresh_token.json",
                body={"user": {"refresh_token": token}}, token=self.tokens.get("access_token")))

    async def request(self, method, path, body=None):
        await self.refresh()
        access = self.tokens["access_token"]
        try:
            return await self._raw(method, DEVICE_URL + path, body=body, token=access)
        except AylaAuthError:
            await self.refresh(force=True, rejected=access)
            return await self._raw(method, DEVICE_URL + path, body=body, token=self.tokens["access_token"])

    async def devices(self):
        data = await self.request("GET", "apiv1/devices.json")
        if not isinstance(data, list) or not all(isinstance(x, dict) and isinstance(x.get("device"), dict) for x in data):
            raise AylaError("Unexpected European device list")
        return [x["device"] for x in data]


class AylaSplit:
    """Only Smart-1-110; every write checks the current cloud property schema."""
    def __init__(self, api, device_id, device_name="Hisense EU AC"):
        self.api = api
        self.device_id = device_id
        self.device_name = device_name
        self.status = {}
        self.properties = {}
        self._command_lock = asyncio.Lock()

    def get_status(self):
        return dict(self.status)

    async def refresh(self):
        await self.api.refresh()
        return True

    async def check_status(self):
        data = await self.api.request("GET", f"apiv1/dsns/{quote(self.device_id, safe='')}/properties.json")
        if not isinstance(data, list) or not all(isinstance(x, dict) and isinstance(x.get("property"), dict) for x in data):
            raise AylaError("Unexpected European property list")
        props = {x["property"].get("name"): x["property"] for x in data}
        packed = props.get("t_control_value", {})
        if packed.get("base_type") != "integer" or "value" not in packed:
            raise AylaError("Missing European packed control state")
        self.status = decode_state(props)
        self.properties = props
        return self.get_status()

    async def command(self, setting, value):
        async with self._command_lock:
            # Refresh before modifying a packed word, including after remote use.
            await self.check_status()
            if setting in ("power", "screen"):
                if type(value) is not bool:
                    raise AylaError("Expected a boolean control")
                name = "t_power" if setting == "power" else "t_backlight"
                encoded = int(value) if setting == "power" else int(not value)
            else:
                name = "t_control_value"
                if setting == "mode":
                    if value not in MODES:
                        raise AylaError("Unsupported European HVAC mode")
                    raw = MODES[value]
                elif setting == "fan":
                    if value not in FANS:
                        raise AylaError("Unsupported European fan mode")
                    raw = FANS[value]
                elif setting == "temperature":
                    if not numeric(value) or not 16 <= value <= 32 or value != int(value):
                        raise AylaError("Temperature must be a whole degree from 16 to 32 C")
                    packed = word(self.properties[name]["value"])
                    raw = int(math.floor(value * 9 / 5 + 32 + 0.5)) if packed & (1 << 31) else int(value)
                else:
                    raise AylaError("Unsupported European control")
                encoded = encode_bits(self.properties[name]["value"], setting, raw)
            prop = self.properties.get(name, {})
            if prop.get("direction") != "input" or prop.get("read_only") is not False:
                raise AylaError("European property does not permit writes")
            expected_type = "integer" if name == "t_control_value" else "boolean"
            if prop.get("base_type") != expected_type:
                raise AylaError("European writable property has an unexpected type")
            path = f"apiv1/dsns/{quote(self.device_id, safe='')}/properties/{name}/datapoints.json"
            result = await self.api.request("POST", path, {"datapoint": {"value": encoded}})
            if not isinstance(result, dict) or not isinstance(result.get("datapoint"), dict):
                raise AylaError("European command was not acknowledged")
            # A cloud acknowledgement is not physical confirmation. Fetch state.
            await self.check_status()
