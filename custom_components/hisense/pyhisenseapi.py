import asyncio
import base64
from collections import Counter
import hashlib
import json
import logging
import time
import uuid

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_LOGGER = logging.getLogger(__name__)

_PORTAL_APP_KEY = "commonweb"
_PORTAL_APP_SECRET = "MORZRbkuiWxjp+SM4vR_GxY4pZxLZ6rn"
_PORTAL_AES_IV = _PORTAL_APP_SECRET[:16].encode("ascii")

WASHER_PHASE_LABELS = {
    0: "standby",
    1: "reservation_wait",
    2: "soaking",
    3: "prewash",
    4: "main_wash",
    5: "rinse",
    6: "spin",
    7: "complete",
    8: "drying",
    9: "air_dry",
    10: "fresh_care",
}
_WASHER_MIN_STATUS_VALUES = 101
_WASHER_TEMPERATURE_LABELS = {
    0: "ambient",
    2: "temperature_20_c",
    3: "temperature_30_c",
    4: "temperature_40_c",
    6: "temperature_60_c",
    9: "temperature_95_c",
}
_WASHER_DRY_SETTING_LABELS = {
    0: "off",
    1: "ready_to_wear",
    2: "ironing",
    3: "storage",
    4: "timed_dry_level_1",
    5: "timed_dry_level_2",
    6: "timed_dry_level_3",
    7: "timed_dry_level_4",
    8: "timed_dry_level_5",
    9: "timed_dry_level_6",
}


class HiSenseLogin:
    def __init__(self, session):
        self.session = session
        self.customer_id = ""

    async def login(self, username, password):
        body_data = {
            "loginName": _HiSenseDevice._encrypt(username),
            "signature": _HiSenseDevice._encrypt(password),
            "serverCode": "9501",
            "distributeId": "2001",
            "termType": 2,
        }
        body = json.dumps(body_data, separators=(",", ":"), ensure_ascii=False)
        params = {
            "lastUpdateTime": "0",
            "version": "1.0",
            "deviceType": "2",
            "appType": "100",
            "versionCode": "101",
            "adaptertRank": "720",
            "_": str(_HiSenseDevice._timestamp()),
        }
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "appKey": _PORTAL_APP_KEY,
            "X-Sign-For": _HiSenseDevice._sign(body),
        }
        async with self.session.post(
            "https://portal-account.hismarttv.com/mobile/se/signon",
            headers=headers,
            data=body,
            params=params,
        ) as response:
            result = await response.json()

        data = result.get("data") or {}
        if data.get("resultCode") != 0:
            return None
        token_info = data.get("tokenInfo") or {}
        access_token = token_info.get("token")
        refresh_token = token_info.get("refreshToken")
        customer_id = (
            token_info.get("customerId")
            or data.get("customerId")
            or result.get("customerId")
        )
        if not access_token or not customer_id:
            return None
        self.customer_id = str(customer_id)
        return str(access_token), refresh_token, self.customer_id

    async def get_home_select_options(self, access_token, customer_id=None):
        customer_id = str(customer_id or self.customer_id)
        body = await _HiSenseDevice._post(
            self.session, access_token, customer_id, "/4.0/iot/home/list", {}
        )
        if not _HiSenseDevice._success(body):
            return None
        homes = (body.get("payload") or {}).get("homes") or []
        options = {}
        for home in homes:
            home_id = home.get("id") or home.get("homeId")
            if not home_id:
                continue
            name = (home.get("name") or home.get("homeName") or "").strip()
            options[str(home_id)] = name or str(home_id)
        return options

    async def get_all_devices(
        self, access_token, home_id, refresh_token, customer_id=None
    ):
        customer_id = str(customer_id or self.customer_id)
        body = await _HiSenseDevice._post(
            self.session,
            access_token,
            customer_id,
            "/4.0/iot/devices/list",
            {"homeId": str(home_id)},
        )
        if not _HiSenseDevice._success(body):
            return None

        devices = {}
        raw_labels = {}
        for device in (body.get("payload") or {}).get("devices") or []:
            if not isinstance(device, dict):
                continue
            device_id = str(device.get("deviceId") or "")
            device_type = _device_type(device)
            if not device_id or device_type is None:
                continue
            partner = device.get("partner") or {}
            partner_id = str(
                partner.get("id") or device.get("partnerId") or "1001"
            )
            product = device.get("product") or {}
            device_name = str(
                device.get("deviceName")
                or device.get("name")
                or product.get("name")
                or ""
            ).strip()
            label = device_name or device_id
            raw_labels[device_id] = label
            devices[device_id] = {
                "device_id": device_id,
                "wifi_id": str(device.get("wifiId") or ""),
                "home_id": str(home_id),
                "refresh_token": refresh_token,
                "access_token": str(access_token),
                "customer_id": customer_id,
                "partner_id": partner_id,
                "device_type": device_type,
                "device_type_name": str(
                    device.get("deviceTypeName")
                    or product.get("name")
                    or device.get("categoryCode")
                    or device_type
                ),
                "device_name": device_name,
                "device_code": str(
                    device.get("deviceCode") or product.get("code") or ""
                ),
                "label": label,
            }

        counts = Counter(raw_labels.values())
        for device_id, label in raw_labels.items():
            if counts[label] > 1:
                devices[device_id]["label"] = f"{label} ({device_id[-6:]})"
        return devices

    async def get_device_wifi_id_and_labels(
        self, access_token, home_id, device_keywords="空调", customer_id=None
    ):
        devices = await self.get_all_devices(
            access_token, home_id, None, customer_id
        )
        if devices is None:
            return None
        selected = {
            device_id: info
            for device_id, info in devices.items()
            if device_keywords in info.get("device_type_name", "")
            or device_keywords in info.get("device_type", "")
        }
        return (
            {device_id: info.get("wifi_id", "") for device_id, info in selected.items()},
            {device_id: info.get("label", device_id) for device_id, info in selected.items()},
        )


def _device_type_from_name(device_type_name) -> str | None:
    if not isinstance(device_type_name, str):
        return None
    text = device_type_name.lower()
    if "aircondition" in text or "air_condition" in text or "空调" in text:
        return "空调"
    if "refrigerat" in text or "fridge" in text or "冰箱" in text:
        return "冰箱"
    if "washer" in text or "washing" in text or "洗衣" in text:
        return "洗衣机"
    return None


def _device_type(device: dict) -> str | None:
    product = device.get("product") or {}
    device_type = _device_type_from_name(
        " ".join(
            str(value or "")
            for value in (
                device.get("categoryCode"),
                device.get("deviceTypeName"),
                product.get("name"),
                product.get("code"),
            )
        )
    )
    return device_type


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _as_bool(value):
    if isinstance(value, str):
        return value.lower() in {"1", "true", "on"}
    return bool(value)


class _HiSenseDevice:
    BASE_URL = "https://iot-aihome.hismarttv.com"
    READ_SOURCE_TYPE = 3
    CONTROL_APP_VERSION = "6.2.18.7"
    CONTROL_SOURCE_TYPE = 20
    CONTROL_SOURCE_NAME = "smartlifeAppH5"
    POWER_SOURCE_NAME = "smartlifeApp"
    LABEL_BATCH_SAVE_PATH = "/4.0/iot/devices/label/batchSave"
    BUZZER_SOUND_LABEL = "buzzer_sound"
    PENDING_CONTROL_TTL = 8.0
    ENERGY_TODAY_PATH = "/4.0/smartHome/databoard/aircondition/todayenergy"

    @staticmethod
    def _encrypt(value: str) -> str:
        raw = value.encode("utf-8")
        padding = 16 - len(raw) % 16
        cipher = Cipher(
            algorithms.AES(_PORTAL_APP_SECRET.encode("ascii")),
            modes.CBC(_PORTAL_AES_IV),
        )
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(raw + bytes([padding]) * padding)
        return base64.b64encode(encrypted + encryptor.finalize()).decode("ascii")

    @staticmethod
    def _sign(body: str) -> str:
        digest = hashlib.md5(
            (body + _PORTAL_APP_SECRET).encode("utf-8"), usedforsecurity=False
        ).digest()
        return base64.b64encode(digest).decode("ascii")

    @staticmethod
    def _timestamp() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def _stringify(value):
        if isinstance(value, dict):
            return {
                str(key): _HiSenseDevice._stringify(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [_HiSenseDevice._stringify(item) for item in value]
        if isinstance(value, (bool, int, float)):
            return str(value)
        return value

    @classmethod
    def _action(cls, command: str, params: dict) -> dict:
        if not isinstance(command, str) or not command:
            raise ValueError("AIHome action command must be a non-empty string")
        if not isinstance(params, dict) or not params:
            raise ValueError("AIHome action params must be a non-empty mapping")
        return {"command": command, "params": cls._stringify(params)}

    @classmethod
    def _request_body(
        cls,
        access_token: str,
        customer_id: str,
        payload,
        *,
        execute=False,
        device_id="",
        partner_id="1001",
        source_name=None,
    ) -> str:
        if execute:
            if not isinstance(payload, list) or not payload:
                raise ValueError("AIHome execute actions must be a non-empty list")
            body = {
                "appVersion": cls.CONTROL_APP_VERSION,
                "payload": {
                    "exclusionFlag": 1,
                    "sourceType": cls.CONTROL_SOURCE_TYPE,
                    "customerId": str(customer_id),
                    "partnerId": str(partner_id),
                    "deviceId": str(device_id),
                    "actions": payload,
                },
                "appType": 1,
                "header": {"messageId": str(uuid.uuid4())},
                "sourceName": source_name or cls.CONTROL_SOURCE_NAME,
                "accessToken": access_token,
            }
        else:
            body = {
                "lastUpdateTime": 0,
                "accessToken": access_token,
                "appVersion": "",
                "openId": "",
                "version": "1.0",
                "deviceType": 2,
                "appType": 100,
                "versionCode": "101",
                "adaptertRank": 720,
                "_": cls._timestamp(),
                "header": {"messageId": str(uuid.uuid4())},
                "payload": {
                    "customerId": str(customer_id),
                    "sourceType": cls.READ_SOURCE_TYPE,
                    **payload,
                },
            }
        return json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def _headers(cls, body: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json",
            "User-Agent": "okhttp/4.10.0",
            "appKey": _PORTAL_APP_KEY,
            "X-Sign-For": cls._sign(body),
        }

    @staticmethod
    def _success(body: dict) -> bool:
        return (
            isinstance(body, dict)
            and body.get("httpCode") not in (401, 403)
            and (body.get("payload") or {}).get("status") == "SUCCESS"
        )

    @classmethod
    async def _post(
        cls,
        session,
        access_token: str,
        customer_id: str,
        path: str,
        payload,
        *,
        execute=False,
        device_id="",
        partner_id="1001",
        source_name=None,
    ) -> dict:
        body = cls._request_body(
            access_token,
            customer_id,
            payload,
            execute=execute,
            device_id=device_id,
            partner_id=partner_id,
            source_name=source_name,
        )
        return await cls._post_raw(session, path, body)

    @classmethod
    async def _post_raw(cls, session, path: str, body: str) -> dict:
        async with session.post(
            f"{cls.BASE_URL}{path}",
            headers=cls._headers(body),
            data=body,
        ) as response:
            result = await response.json()
            if getattr(response, "status", None) in (401, 403) and isinstance(result, dict):
                return {**result, "httpCode": response.status}
            return result

    @classmethod
    async def _post_parameters(cls, session, path: str, parameters: dict) -> dict:
        """Post the flat parameter body used by the dashboard endpoints."""
        body = json.dumps(parameters, separators=(",", ":"), ensure_ascii=False)
        return await cls._post_raw(session, path, body)

    @classmethod
    def _label_request_body(
        cls,
        access_token: str,
        device_id: str,
        partner_id: str,
        label_key: str,
        label_value,
    ) -> str:
        body = {
            "accessToken": access_token,
            "deviceId": str(device_id),
            "header": {
                "languageId": 0,
                "messageId": str(uuid.uuid4()),
                "timestamp": cls._timestamp(),
            },
            "appVersion": cls.CONTROL_APP_VERSION,
            "payload": {
                "labels": [
                    {
                        "partnerId": str(partner_id),
                        "devId": str(device_id),
                        "labelKey": str(label_key),
                        "labelValue": str(label_value),
                    }
                ]
            },
        }
        return json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    def __init__(
        self,
        wifi_id,
        device_id,
        refresh_token,
        session,
        device_name="",
        entity_name="",
        *,
        home_id="",
        access_token=None,
        customer_id="",
        partner_id="1001",
        username="",
        password="",
        on_token_refresh=None,
        token_lock=None,
    ):
        self.wifi_id = wifi_id
        self.device_id = device_id
        self.home_id = str(home_id or "")
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.customer_id = str(customer_id or "")
        self.partner_id = str(partner_id or "1001")
        self.username = username
        self.password = password
        self.session = session
        self.device_name = device_name
        self.entity_name = entity_name
        self.status = {}
        self._pending_status = {}
        self._on_token_refresh = on_token_refresh
        self.on_auth_failure = None
        self._token_lock = token_lock or asyncio.Lock()

    def _notify_auth_failure(self) -> None:
        """Start status recovery after an authenticated control is rejected."""
        if self.on_auth_failure:
            self.on_auth_failure()

    async def refresh(self, *, force=False, previous_token=None):
        """Sign in through the AIHome account service when needed."""
        if self.access_token and not force:
            return True
        if not self.username or not self.password:
            return False
        async with self._token_lock:
            if previous_token is not None and self.access_token != previous_token:
                return True
            try:
                tokens = await HiSenseLogin(self.session).login(
                    self.username, self.password
                )
            except Exception:
                _LOGGER.warning("Hisense AIHome sign-in request failed", exc_info=True)
                return False
            if not tokens:
                _LOGGER.warning("Hisense AIHome sign-in was rejected")
                return False
            self.access_token, self.refresh_token, self.customer_id = tokens
            if self._on_token_refresh:
                self._on_token_refresh(
                    self.access_token, self.refresh_token, self.customer_id
                )
            return True

    @staticmethod
    def _auth_failure(body) -> bool:
        if not isinstance(body, dict):
            return False
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
        response = body.get("response") if isinstance(body.get("response"), dict) else {}
        fields = (body, payload, response)
        codes = {
            str(node[key]).lower()
            for node in fields
            for key in ("errorCode", "resultCode", "httpCode")
            if node.get(key) is not None
        }
        if codes & {"401", "403"}:
            return True
        reason = " ".join(
            str(node.get(key, ""))
            for node in fields
            for key in ("status", "errorCode", "errorDesc", "message", "desc")
        ).lower()
        return any(
            word in reason
            for word in ("token", "unauthoriz", "authentication", "登录过期", "令牌", "鉴权")
        )

    async def _send_aihome_action(self, command, params, *, source_name=None):
        if not await self.refresh():
            return False
        action = self._action(command, params)
        for attempt in range(2):
            request_token = self.access_token
            try:
                result = await self._post(
                    self.session, request_token, self.customer_id,
                    "/4.0/iot/devices/execute", [action], execute=True,
                    device_id=self.device_id, partner_id=self.partner_id,
                    source_name=source_name,
                )
            except Exception:
                _LOGGER.error("Hisense AIHome control request failed", exc_info=True)
                return False
            if self._success(result):
                return True
            if (
                attempt == 0
                and self._auth_failure(result)
                and await self.refresh(force=True, previous_token=request_token)
            ):
                continue
            if self._auth_failure(result):
                self._notify_auth_failure()
            _LOGGER.warning(
                "Hisense AIHome control failed: %s",
                self._response_summary(result),
            )
            return False
        return False

    async def _send_aihome_label(self, label_key: str, label_value) -> bool:
        if not await self.refresh():
            return False
        for attempt in range(2):
            request_token = self.access_token
            body = self._label_request_body(
                request_token, self.device_id, self.partner_id,
                label_key, label_value,
            )
            try:
                result = await self._post_raw(
                    self.session, self.LABEL_BATCH_SAVE_PATH, body,
                )
            except Exception:
                _LOGGER.error("Hisense AIHome label request failed", exc_info=True)
                return False
            if self._success(result) or self._label_success(result):
                return True
            if (
                attempt == 0
                and self._auth_failure(result)
                and await self.refresh(force=True, previous_token=request_token)
            ):
                continue
            if self._auth_failure(result):
                self._notify_auth_failure()
            _LOGGER.warning(
                "Hisense AIHome label update failed: %s",
                self._response_summary(result),
            )
            return False
        return False

    def _response_summary(self, body) -> dict:
        """Return a safe failure summary without tokens or signatures."""
        if not isinstance(body, dict):
            return {"response_type": type(body).__name__}
        payload = body.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        response = body.get("response")
        if not isinstance(response, dict):
            response = {}
        error_desc = payload.get("errorDesc") or response.get("desc") or body.get("desc")
        if error_desc is not None:
            error_desc = str(error_desc)[:300]
            for secret in (self.access_token, self.refresh_token):
                if secret:
                    error_desc = error_desc.replace(str(secret), "[redacted]")
        return {
            "status": payload.get("status"),
            "httpCode": body.get("httpCode"),
            "errorCode": (
                payload.get("errorCode")
                or response.get("resultCode")
                or body.get("resultCode")
            ),
            "errorDesc": error_desc,
        }

    @staticmethod
    def _label_success(body: dict) -> bool:
        if not isinstance(body, dict):
            return False
        result_code = body.get("resultCode")
        if result_code in (0, "0"):
            return True
        payload = body.get("payload") or {}
        return payload.get("resultCode") in (0, "0")

    async def check_status(self):
        if not await self.refresh():
            return None
        try:
            result = await self._post(
                self.session, self.access_token, self.customer_id,
                "/4.0/iot/devices/detail",
                {"deviceId": str(self.device_id), "partnerId": str(self.partner_id)},
            )
        except Exception:
            _LOGGER.error("Hisense AIHome status request failed", exc_info=True)
            return None
        if not self._success(result):
            _LOGGER.warning("Hisense AIHome status failed: %s", self._response_summary(result))
            return None
        payload = result.get("payload") or {}
        device = payload.get("device") or {}
        states = device.get("states") or payload.get("states") or {}
        if not isinstance(states, dict):
            return None
        fresh_keys = self._update_from_states(states) or set()
        if self._update_prompt_sound_from_detail(result):
            fresh_keys.add("prompt_sound")
        self._reconcile_pending_status(fresh_keys)
        return self.get_status()

    def _update_from_states(self, states: dict):
        updates = {
            key: states[key]
            for key in ("onlineStatus", "powerStatus")
            if key in states
        }
        self.status.update(updates)
        return set(updates)

    def _update_status_from_aihome(self, detail: dict):
        states = detail.get("states") or {}
        if not isinstance(states, dict):
            return False
        fresh_keys = self._update_from_states(states) or set()
        if self._update_prompt_sound_from_detail(detail):
            fresh_keys.add("prompt_sound")
        self._reconcile_pending_status(fresh_keys)
        return True

    @classmethod
    def _find_label_value(cls, node, label_key: str):
        if isinstance(node, dict):
            if node.get("labelKey") == label_key:
                return node.get("labelValue")
            # The device detail API uses key/value, while label writes use
            # labelKey/labelValue.
            if node.get("key") == label_key:
                return node.get("value")
            for value in node.values():
                found = cls._find_label_value(value, label_key)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = cls._find_label_value(value, label_key)
                if found is not None:
                    return found
        return None

    def _update_prompt_sound_from_detail(self, detail: dict) -> bool:
        label_value = self._find_label_value(detail, self.BUZZER_SOUND_LABEL)
        if label_value is None:
            return False
        self.status["prompt_sound"] = _as_bool(label_value)
        return True

    def _reconcile_pending_status(self, fresh_keys):
        now = time.monotonic()
        for key, (expected, expires_at) in list(self._pending_status.items()):
            if key not in fresh_keys:
                if now < expires_at:
                    self.status[key] = expected
                else:
                    self._pending_status.pop(key, None)
            elif self.status.get(key) == expected:
                self._pending_status.pop(key, None)
            elif now >= expires_at:
                self._pending_status.pop(key, None)
            else:
                self.status[key] = expected

    def _set_pending_status(self, updates: dict):
        expires_at = time.monotonic() + self.PENDING_CONTROL_TTL
        self.status.update(updates)
        for key, value in updates.items():
            self._pending_status[key] = (value, expires_at)

    def get_status(self):
        return dict(self.status)

    @staticmethod
    def _energy_data(body: dict) -> dict:
        """Unwrap both the native bridge and direct server response shapes."""
        node = body
        energy_keys = {
            "todayEnergy",
            "runTime",
        }
        for _ in range(4):
            if not isinstance(node, dict):
                return {}
            if energy_keys.intersection(node):
                return node
            next_node = node.get("data")
            if not isinstance(next_node, dict):
                next_node = node.get("payload")
            if not isinstance(next_node, dict):
                return {}
            node = next_node
        return {}

    async def refresh_energy(self):
        """Read today's AC energy and accumulated runtime."""
        if not await self.refresh() or not self.home_id:
            return None

        parameters = {
            "accessToken": self.access_token,
            "deviceId": str(self.device_id),
            "homeId": self.home_id,
            "partnerId": str(self.partner_id),
            "wifiId": str(self.wifi_id),
        }
        try:
            today_body = await self._post_parameters(
                self.session, self.ENERGY_TODAY_PATH, parameters
            )
        except Exception:
            _LOGGER.error("Hisense AIHome energy request failed", exc_info=True)
            return None

        today_data = self._energy_data(today_body)
        values = {
            "today_energy": _as_number(today_data.get("todayEnergy")),
            "run_time": _as_number(today_data.get("runTime")),
        }
        if not any(value is not None for value in values.values()):
            _LOGGER.warning("Hisense AIHome energy response did not contain data")
            return None

        self.status.update(
            {key: value for key, value in values.items() if value is not None}
        )
        return self.get_status()


class HiSenseWasher(_HiSenseDevice):
    """Read-only AIHome client for Hisense washers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status = {
            "protocol_payload_length": 0,
            "protocol_payload_sha256": "",
            "protocol_raw_values": [],
            "protocol_changed_indices": [],
            "protocol_nonzero_values": {},
        }

    @classmethod
    def _status_success(cls, result) -> bool:
        if cls._success(result):
            return True
        if not isinstance(result, dict):
            return False
        if result.get("httpCode") in (401, 403):
            return False
        payload = result.get("payload")
        if isinstance(payload, dict) and "status" in payload:
            return False
        response = result.get("response")
        return isinstance(response, dict) and isinstance(
            response.get("deviceStatusList"), list
        )

    @classmethod
    def _extract_status_values(cls, result) -> list[int]:
        if not isinstance(result, dict):
            raise ValueError("missing response object")

        payload = result.get("payload") or {}
        raw_status = payload.get("deviceStatus") if isinstance(payload, dict) else None
        if raw_status is None:
            response = result.get("response") or {}
            status_list = (
                response.get("deviceStatusList")
                if isinstance(response, dict)
                else None
            )
            if isinstance(status_list, list) and status_list:
                first_status = status_list[0]
                if isinstance(first_status, dict):
                    raw_status = first_status.get("deviceStatus")

        if isinstance(raw_status, str):
            values = [int(value.strip()) for value in raw_status.split(",")]
        elif isinstance(raw_status, list):
            values = [int(value) for value in raw_status]
        else:
            raise ValueError("missing deviceStatus")

        if len(values) < _WASHER_MIN_STATUS_VALUES:
            raise ValueError(
                f"washer status has {len(values)} values; expected at least "
                f"{_WASHER_MIN_STATUS_VALUES}"
            )
        return values

    def _update_status_from_result(self, result) -> bool:
        try:
            values = self._extract_status_values(result)
        except (TypeError, ValueError):
            _LOGGER.error("Failed to parse Hisense washer status", exc_info=True)
            return False

        previous = self.status.get("protocol_raw_values", [])
        changed = (
            [
                index
                for index in range(max(len(previous), len(values)))
                if (previous[index] if index < len(previous) else None)
                != (values[index] if index < len(values) else None)
            ]
            if previous
            else []
        )
        canonical = ",".join(str(value) for value in values)
        phase = values[11]
        power_on = values[9] == 1
        run_state = values[8]
        if not power_on:
            machine_state = "off"
        elif phase == 7:
            machine_state = "complete"
        elif run_state == 1:
            machine_state = "running"
        elif run_state == 0 and phase == 0:
            machine_state = "standby"
        elif run_state == 0:
            machine_state = "paused"
        else:
            machine_state = f"unknown_{run_state}"

        self.status = {
            "machine_state": machine_state,
            "run_state": run_state,
            "power_on": power_on,
            "phase": phase,
            "phase_label": WASHER_PHASE_LABELS.get(phase, f"unknown_{phase}"),
            "program": values[12],
            "remaining_minutes": values[28] * 256 + values[29],
            "gate_locked": values[6] == 1,
            "fault": values[27],
            "motor_speed": values[13] * 256 + values[14],
            "temperature_raw": values[15],
            "configured_spin": values[37] * 100,
            "configured_temperature": _WASHER_TEMPERATURE_LABELS.get(
                values[38], f"unknown_{values[38]}"
            ),
            "child_lock": values[100] == 1,
            "dry_setting": _WASHER_DRY_SETTING_LABELS.get(
                values[80], f"unknown_{values[80]}"
            ),
            "protocol_payload_length": len(values),
            "protocol_payload_sha256": hashlib.sha256(
                canonical.encode()
            ).hexdigest(),
            "protocol_raw_values": values,
            "protocol_changed_indices": changed,
            "protocol_nonzero_values": {
                str(index): value
                for index, value in enumerate(values)
                if value != 0
            },
        }
        _LOGGER.debug(
            "Hisense washer status: length=%s sha256=%s changed_indices=%s",
            len(values),
            self.status["protocol_payload_sha256"],
            changed,
        )
        return True

    async def check_status(self):
        if not await self.refresh():
            return None
        try:
            result = await self._post(
                self.session, self.access_token, self.customer_id,
                "/4.0/iot/devices/detail",
                {"deviceId": str(self.device_id), "partnerId": str(self.partner_id)},
            )
        except Exception:
            _LOGGER.error("Hisense AIHome washer status request failed", exc_info=True)
            return None
        if not self._status_success(result):
            _LOGGER.warning("Hisense AIHome washer status failed: %s", self._response_summary(result))
            return None
        if not self._update_status_from_result(result):
            return None
        return self.get_status()

    async def _send_aihome_action(self, command, params, *, source_name=None):
        """Keep washer support read-only even if an inherited method is called."""
        return False

    async def _send_aihome_label(self, label_key: str, label_value) -> bool:
        """Keep washer support read-only even if an inherited method is called."""
        return False

    def get_status(self):
        return json.loads(json.dumps(self.status))


class HiSenseAC(_HiSenseDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hvac_mode_lookup = {
            0: "FAN_ONLY",
            1: "HEAT",
            2: "COOL",
            3: "DRY",
            4: "AUTO",
        }
        self.fan_mode_lookup = {
            1: "DIFFUSE",
            2: "LOW",
            3: "MEDIUM",
            4: "HIGH",
        }
        self.climate_min_temp = 16
        self.climate_max_temp = 32

    def _update_from_states(self, states: dict):
        mode_id = _as_int(
            states.get("modes", states.get("workMode", states.get("mode")))
        )
        fan_id = None if _as_bool(states.get("autoWind")) else _as_int(states.get("windSpeed"))
        status = {}
        if "onlineStatus" in states:
            status["onlineStatus"] = states["onlineStatus"]
        if "powerStatus" in states:
            status["power_on"] = _as_bool(states["powerStatus"])
        if mode_id is not None:
            status["hvac_mode_id"] = mode_id
            status["hvac_mode"] = self.hvac_mode_lookup.get(mode_id)
        desired_temperature = _as_number(
            states.get("setTemperature", states.get("desiredTemperature"))
        )
        if desired_temperature is not None:
            status["desired_temperature"] = desired_temperature
        indoor_temperature = _as_number(
            states.get("realTemperature", states.get("indoorTemperature"))
        )
        if indoor_temperature is not None:
            status["indoor_temperature"] = indoor_temperature
        if fan_id is not None:
            status["fan_mode_id"] = fan_id
            status["fan_mode"] = self.fan_mode_lookup.get(fan_id)
        if "screenSwitch" in states:
            status["screen_on"] = _as_bool(states["screenSwitch"])
        if "heatSwitch" in states:
            status["aux_heat"] = _as_bool(states["heatSwitch"])
        if "natrueWind" in states or "natureWind" in states:
            status["nature_wind"] = _as_bool(
                states.get("natrueWind", states.get("natureWind"))
            )
        if "autoWind" in states:
            status["auto_wind"] = _as_bool(states["autoWind"])
        if "leftRightWind" in states:
            status["left_right_wind"] = _as_int(states["leftRightWind"])
        if "leftRightWindFullControl" in states:
            status["left_right_wind_full_control"] = _as_bool(
                states["leftRightWindFullControl"]
            )
        if "fastCoolHeatSwitch" in states:
            status["fast_cool_heat"] = _as_bool(states["fastCoolHeatSwitch"])
        status = {key: value for key, value in status.items() if value is not None}
        self.status.update(status)
        return set(status)

    def _optimistic_control_update(self, command: str, params: dict):
        updates = {}

        def value_for(key):
            value = params.get(key)
            if isinstance(value, dict):
                return value.get("value")
            return value

        if command == "connector.device.command.Power":
            code = (params.get("onAndOff") or {}).get("code")
            if code in ("On", "Off"):
                updates["power_on"] = code == "On"
        elif command == "connector.device.command.SetTemperature":
            value = _as_number(value_for("setTemperature"))
            if value is not None:
                updates["desired_temperature"] = value
        elif command == "connector.device.command.SetWindSpeed":
            auto_wind = value_for("autoWind")
            if auto_wind is not None:
                updates["auto_wind"] = _as_bool(auto_wind)
            wind_speed = _as_int(value_for("windSpeed"))
            if wind_speed is not None:
                updates["fan_mode_id"] = wind_speed
                updates["fan_mode"] = self.fan_mode_lookup.get(wind_speed)
        elif command == "connector.device.command.SetModes":
            mode_id = _as_int(value_for("modes"))
            if mode_id is not None:
                updates["hvac_mode_id"] = mode_id
                updates["hvac_mode"] = self.hvac_mode_lookup.get(mode_id)
        elif command == "connector.device.command.SetScreenSwitch":
            updates["screen_on"] = _as_bool(value_for("screenSwitch"))
        elif command == "connector.device.command.SetHeatSwitch":
            updates["aux_heat"] = _as_bool(value_for("heatSwitch"))
        elif command == "connector.device.command.SetLeftRightWindFullControl":
            updates["left_right_wind_full_control"] = _as_bool(
                value_for("leftRightWindFullControl")
            )
        elif command == "connector.device.command.SetFastCoolHeatSwitch":
            updates["fast_cool_heat"] = _as_bool(value_for("fastCoolHeatSwitch"))
        elif command == "connector.device.command.SetNatrueWind":
            updates["nature_wind"] = _as_bool(value_for("natrueWind"))

        if updates:
            self._set_pending_status(updates)

    async def _control(self, command, params, *, source_name=None):
        if source_name is None:
            success = await self._send_aihome_action(command, params)
        else:
            success = await self._send_aihome_action(
                command, params, source_name=source_name
            )
        if success:
            self._optimistic_control_update(command, params)
        return success

    async def turn_on(self):
        return await self._control(
            "connector.device.command.Power",
            {"onAndOff": {"code": "On"}},
            source_name=self.POWER_SOURCE_NAME,
        )

    async def turn_off(self):
        return await self._control(
            "connector.device.command.Power",
            {"onAndOff": {"code": "Off"}},
            source_name=self.POWER_SOURCE_NAME,
        )

    async def set_temperature(self, temperature):
        return await self._control(
            "connector.device.command.SetTemperature",
            {"setTemperature": {"value": temperature}},
        )

    async def set_fan_mode(self, fan_mode_id):
        return await self._control(
            "connector.device.command.SetWindSpeed",
            {"windSpeed": fan_mode_id},
        )

    async def set_hvac_mode(self, mode_id):
        return await self._control(
            "connector.device.command.SetModes",
            {"modes": {"value": mode_id}},
        )

    async def set_screen_switch(self, enabled):
        return await self._control(
            "connector.device.command.SetScreenSwitch",
            {"screenSwitch": {"value": int(enabled)}},
        )

    async def set_heat_switch(self, enabled):
        return await self._control(
            "connector.device.command.SetHeatSwitch",
            {"heatSwitch": {"value": int(enabled)}},
        )

    async def set_swing_mode(self, enabled: bool):
        return await self._control(
            "connector.device.command.SetLeftRightWindFullControl",
            {"leftRightWindFullControl": {"value": int(enabled)}},
        )

    async def set_fast_cool_heat(self, enabled: bool):
        return await self._control(
            "connector.device.command.SetFastCoolHeatSwitch",
            {"fastCoolHeatSwitch": {"value": int(enabled)}},
        )

    async def set_nature_wind(self, enabled: bool):
        return await self._control(
            "connector.device.command.SetNatrueWind",
            {"natrueWind": {"value": int(enabled)}},
        )

    async def set_auto_wind(self, enabled: bool):
        return await self._control(
            "connector.device.command.SetWindSpeed",
            {"autoWind": {"value": int(enabled)}},
        )

    async def set_prompt_sound(self, enabled: bool):
        if not await self._send_aihome_label(
            self.BUZZER_SOUND_LABEL,
            int(enabled),
        ):
            return False
        self._set_pending_status({"prompt_sound": bool(enabled)})
        return True

    async def get_energy(self):
        return await self.refresh_energy()


class HiSenseFridge(_HiSenseDevice):
    """Read refrigerator temperatures when AIHome exposes a status array."""

    async def check_status(self):
        if not await self.refresh():
            return None
        try:
            result = await self._post(
                self.session, self.access_token, self.customer_id,
                "/4.0/iot/devices/detail",
                {"deviceId": str(self.device_id), "partnerId": str(self.partner_id)},
            )
        except Exception:
            _LOGGER.error("Hisense AIHome fridge status request failed", exc_info=True)
            return None
        if not self._success(result):
            _LOGGER.warning(
                "Hisense AIHome fridge status failed: %s",
                self._response_summary(result),
            )
            return None

        payload = result.get("payload") or {}
        device = payload.get("device") or {}
        states = device.get("states") or payload.get("states") or {}
        if not isinstance(states, dict):
            states = {}
        self._update_from_states(states)

        # Issue #14 documents these positions for a legacy status array. Only
        # interpret them when the AIHome detail response carries that same array.
        raw = next(
            (
                node.get("deviceStatus")
                for node in (states, device, payload)
                if isinstance(node, dict) and node.get("deviceStatus") is not None
            ),
            None,
        )
        if isinstance(raw, str):
            parts = raw.split(",")
        elif isinstance(raw, list):
            parts = raw
        else:
            parts = []
        if len(parts) > 9:
            try:
                values = [int(str(parts[index]).strip()) for index in (0, 1, 9)]
            except (TypeError, ValueError):
                _LOGGER.warning("Hisense AIHome fridge status array has invalid temperatures")
            else:
                if 1 <= values[0] <= 10 and -25 <= values[1] <= -15:
                    self.status.update(
                        refrigerator_temperature=values[0],
                        freezer_temperature=values[1],
                        ambient_temperature=values[2],
                    )
                else:
                    _LOGGER.warning("Hisense AIHome fridge status array is outside known ranges")
        return self.get_status() if self.status else None

    unsupported_features = frozenset(
        {
            "power",
            "refrigerator_temperature",
            "freezer_temperature",
            "work_mode",
            "variation_mode",
        }
    )

    async def turn_on(self):
        return False

    async def turn_off(self):
        return False

    async def set_refrigerator_temperature(self, temperature: int):
        return False

    async def set_freeze_temperature(self, temperature: int):
        return False

    async def set_work_mode(self, mode_id: int):
        return False

    async def set_fridge_mode(self, mode_id: int):
        return False

    async def set_variation_mode(self, mode_id: int):
        return False
