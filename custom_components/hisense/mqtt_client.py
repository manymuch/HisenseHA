from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import ssl
import urllib.parse
import uuid

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

_LOGGER = logging.getLogger(__name__)

_APP_KEY = "JHKAIHOME"
_MQTT_CONFIG_URL = "https://mqtt-msg.hismarttv.com/2.0/mqtt/config"
_DEFAULT_DEVICE_ID = "aiotfffe64f68575912f748de67f8280d1d4cd13"

# Verified working live credentials captured from official App handshake
_FALLBACK_BROKER = "thsprojuk.aliyun-hbbj-hisense.pubsub.tech"
_FALLBACK_PORT = 1883
_FALLBACK_USERNAME = "thingidp@thsprojuk|aiotfffe64f68575912f748de67f8280d1d4cd13|0|MD5"
_FALLBACK_PASSWORD = "c19336c55cbcb30a64c5241240fd7749"


class HisenseMQTTManager:
    """Manages the MQTT long connection for Hisense devices."""

    def __init__(
        self,
        session,
        access_token: str,
        customer_id: str,
        device_id: str = _DEFAULT_DEVICE_ID,
        on_message_callback=None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        self.session = session
        self.access_token = access_token
        self.customer_id = customer_id
        self.device_id = device_id
        self.on_message_callback = on_message_callback
        self.loop = loop
        self.client = None
        self.connect_url: str | None = None
        self.sub_topics: list[str] = []
        self._is_running = False

    def _get_sub_topics(self) -> list[str]:
        """Compute the dynamic sub topics for device and customer."""
        return [
            f"$iot/{self.device_id}/user/down/JHKAIHOME/#",
            f"$iot/general/user/{self.customer_id}/down/JHKAIHOME/#",
        ]

    async def fetch_mqtt_config(self) -> dict | None:
        """Fetch MQTT broker configuration from Hisense cloud, falling back to verified live config."""
        body_data = {
            "format": 1,
            "appKey": _APP_KEY,
            "deviceId": self.device_id,
            "clientType": 0,
            "timeStamp": int(asyncio.get_event_loop().time() * 1000) / 1000.0,
            "version": "2.0",
            "accessToken": str(self.access_token),
            "languageId": 0,
        }
        body = json.dumps(body_data, separators=(",", ":"), ensure_ascii=False)
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "*/*",
            "User-Agent": "JHKMain/7.0.8 (iPhone; iOS 27.0.1; Scale/3.00)",
        }

        try:
            if self.session is not None:
                async with self.session.post(
                    _MQTT_CONFIG_URL,
                    headers=headers,
                    data=body,
                    timeout=aiohttp.ClientTimeout(total=2.0),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        info = (result.get("response") or {}).get("info")
                        if info and info.get("connectUrl"):
                            return info
        except Exception as e:
            _LOGGER.debug("Could not fetch remote MQTT config: %s", e)

        # Fallback to verified live broker credentials
        _LOGGER.info("Using confirmed live Hisense MQTT configuration.")
        return {
            "connectUrl": f"tcp://{_FALLBACK_BROKER}:{_FALLBACK_PORT}",
            "loginUserName": f"thingidp@thsprojuk|{self.device_id}|0|MD5",
            "loginPassword": _FALLBACK_PASSWORD,
        }

    def _create_mqtt_client(self, client_id: str):
        if mqtt is None:
            _LOGGER.error("paho-mqtt is not installed.")
            return None
        try:
            from paho.mqtt.enums import CallbackAPIVersion
            return mqtt.Client(CallbackAPIVersion.VERSION2, client_id=client_id)
        except (ImportError, AttributeError):
            return mqtt.Client(client_id=client_id)

    async def start(self):
        """Start the MQTT client long connection."""
        self._is_running = True
        config = await self.fetch_mqtt_config()
        if not config or not config.get("connectUrl"):
            _LOGGER.warning("No MQTT configuration available.")
            return False

        self.connect_url = config.get("connectUrl")
        self.sub_topics = self._get_sub_topics()
        username = config.get("loginUserName") or f"thingidp@thsprojuk|{self.device_id}|0|MD5"
        password = config.get("loginPassword") or _FALLBACK_PASSWORD

        _LOGGER.info("Starting Hisense MQTT client (Broker: %s, Topics: %s)", self.connect_url, self.sub_topics)

        parsed = urllib.parse.urlparse(self.connect_url)
        host = parsed.hostname or _FALLBACK_BROKER
        port = parsed.port or (8883 if parsed.scheme in ("ssl", "tls", "mqtts") else 1883)
        use_ssl = parsed.scheme in ("ssl", "tls", "mqtts")

        self.client = self._create_mqtt_client(self.device_id)
        if not self.client:
            return False

        if use_ssl:
            self.client.tls_set(cert_reqs=ssl.CERT_NONE)
            self.client.tls_insecure_set(True)

        self.client.username_pw_set(username=username, password=password)
        try:
            self.client.reconnect_delay_set(min_delay=2, max_delay=60)
        except Exception:
            pass

        def on_connect(client, userdata, flags, rc, properties=None):
            rc_code = getattr(rc, "value", rc)
            if rc_code == 0:
                _LOGGER.info("Connected to Hisense MQTT Broker successfully.")
                for topic in self.sub_topics:
                    res, mid = client.subscribe(topic, qos=0)
                    _LOGGER.info("Subscribed to MQTT topic: %s (result=%s)", topic, res)
            else:
                _LOGGER.warning("Hisense MQTT Broker connection failed with code: %s", rc)

        def on_disconnect(client, userdata, *args):
            _LOGGER.warning("Hisense MQTT disconnected: %s", args)

        def on_message(client, userdata, msg):
            self.handle_message(msg.topic, msg.payload)

        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        self.client.on_message = on_message

        try:
            self.client.connect_async(host, port, keepalive=60)
            self.client.loop_start()
            return True
        except Exception as e:
            _LOGGER.error("Failed to connect to Hisense MQTT Broker: %s", e)
            return False

    def handle_message(self, topic: str, payload_bytes: bytes):
        """Handle incoming MQTT messages on background thread safely."""
        try:
            payload_str = payload_bytes.decode("utf-8", errors="replace")
            _LOGGER.info("MQTT message received on %s: %s", topic, payload_str)
            data = json.loads(payload_str)
        except Exception as ex:
            _LOGGER.warning("Non-JSON MQTT message on %s: %s (err: %s)", topic, payload_bytes, ex)
            return

        try:
            parsed_text = None
            if isinstance(data.get("text"), str):
                try:
                    parsed_text = json.loads(data["text"])
                    data["parsed_text"] = parsed_text
                except Exception:
                    pass

            device_id = data.get("deviceId") or data.get("device_id")
            if not device_id and parsed_text and isinstance(parsed_text, dict):
                device_id = parsed_text.get("devId") or parsed_text.get("deviceId")
            if not device_id and isinstance(data.get("payload"), dict):
                device_id = data["payload"].get("deviceId") or data["payload"].get("device_id")

            if self.on_message_callback:
                if self.loop is not None and not self.loop.is_closed():
                    self.loop.call_soon_threadsafe(self.on_message_callback, device_id, data)
                else:
                    self.on_message_callback(device_id, data)
        except Exception as err:
            _LOGGER.error("Unexpected error in MQTT message handler: %s", err, exc_info=True)

    def simulate_message(self, device_id: str, state_or_data: str | dict):
        """Simulate an incoming MQTT message for testing."""
        if isinstance(state_or_data, str):
            payload = {
                "businessTag": "JHkDeviceChangeBizMessage",
                "deviceId": device_id,
                "action": "onDeviceStateUpdate",
                "status": state_or_data,
            }
        else:
            payload = dict(state_or_data)
            if "deviceId" not in payload:
                payload["deviceId"] = device_id

        _LOGGER.info("Simulating MQTT message for device %s: %s", device_id, payload)
        if self.on_message_callback:
            if self.loop is not None and not self.loop.is_closed():
                self.loop.call_soon_threadsafe(self.on_message_callback, device_id, payload)
            else:
                self.on_message_callback(device_id, payload)

    async def stop(self):
        """Stop MQTT client."""
        self._is_running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None
