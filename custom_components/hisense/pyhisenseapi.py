from collections import Counter
from copy import deepcopy
import time
import logging
_LOGGER = logging.getLogger(__name__)

_STATUS_SWING_MODES = {0, 1, 2, 3}
_MIN_STATUS_VALUES = 210
_MIN_FRIDGE_STATUS_VALUES = 130


def _device_type_from_name(device_type_name) -> str | None:
    if not isinstance(device_type_name, str):
        return None
    if "空调" in device_type_name:
        return "空调"
    if "冰箱" in device_type_name:
        return "冰箱"
    return None


def _device_text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _device_select_label(device: dict, device_id: str) -> str:
    room = _device_text(device.get("roomName"))
    nick = _device_text(device.get("deviceNickName"))
    if room and nick:
        return f"{room}-{nick}"
    if room:
        return room
    if nick:
        return nick
    device_name = _device_text(device.get("deviceName"))
    if device_name:
        return device_name
    return device_id


class HiSenseLogin:
    def __init__(self, session):
        self.session = session
    
    def get_timestamp(self):
        return int(time.time() * 1000)

    async def login(self, username, password):
        timestamp = self.get_timestamp()
        url='https://portal-account.hismarttv.com/mobile/signon'
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
        }
        data = {
            'pdateTime': '0',
            'version': '1.0',
            'deviceType': '2',
            'appType': '100',
            'versionCode': '101',
            'adaptertRank': '3098',
            'deviceType':'1',
            'distributeId':'2001',
            'loginName': username,
            'serverCode':'9501',
            'signature': password,
        }
        params = {
            'lastUpdateTime': '0',
            'version': '1.0',
            'deviceType': '2',
            'appType': '100',
            'versionCode': '101',
            'adaptertRank': '4130',
            '_': str(timestamp),
        }
        async with self.session.post(url, headers=headers, json=data, params=params) as response:
            result = await response.json()
            result_code = result["data"]["resultCode"]
            if result_code == 0:
                access_token = result["data"]["tokenInfo"]["token"]
                refresh_token = result["data"]["tokenInfo"]["refreshToken"]
                return access_token, refresh_token
            else:
                return None

    async def get_home_select_options(self, access_token):
        """Return mapping home_id -> display name for config flow UI."""
        timestamp = self.get_timestamp()
        url='https://api-wg.hismarttv.com/wg/dm/getHomeList'
        
        headers = {
                'Host': 'api.wg.hismarttv.com',
                'Connection': 'Keep-Alive',
                'Accept-Encoding': 'gzip',
                'User-Agent': 'okhttp/4.10.0',
            }
        params = {
            'sign': '',
            'languageId': '0',
            'version': '8.0',
            'accessToken': access_token,   
            'timezone':'28800',
            'format': '1',
            'timeStamp': str(timestamp),
        }
        async with self.session.get(url, headers=headers, params=params) as response:
            result = await response.json()
            result_code = result["response"]["resultCode"]
            if result_code == 0:
                home_list = result["response"]["homeList"]
                options = {}
                for home in home_list:
                    hid = home["homeId"]
                    name = (home.get("homeName") or "").strip()
                    options[hid] = name if name else hid
                return options
            else:
                return None

    async def get_device_wifi_id_and_labels(
        self, access_token, home_id, device_keywords="空调"
    ):
        """Return (device_id -> wifi_id, device_id -> UI label) for filtered devices."""
        timestamp = self.get_timestamp()
        url='https://api-wg.hismarttv.com/wg/dm/getHomeDeviceList'
        headers = {
                'Host': 'api-wg.hismarttv.com',
                'Connection': 'Keep-Alive',
                'Accept-Encoding': 'gzip',
                'User-Agent': 'okhttp/4.10.0',
            }
        params = {
            'sign': '',
            'languageId': '0',
            'version': '8.0',
            'accessToken': access_token,   
            'homeId': home_id,
            'timezone':'28800',
            'format': '1',
            'timeStamp': str(timestamp),
        }
        async with self.session.get(url, headers=headers, params=params) as response:
            result = await response.json()
            result_code = result["response"]["resultCode"]
            if result_code == 0:
                device_list = result["response"]["deviceList"]
                device_wifi_id_dict = {}
                raw_labels = {}
                for device in device_list:
                    device_type_name = device["deviceTypeName"]
                    if device_keywords in device_type_name:
                        did = device["deviceId"]
                        device_wifi_id_dict[did] = device["wifiId"]
                        raw_labels[did] = _device_select_label(device, did)
                label_counts = Counter(raw_labels.values())
                device_id_to_label = {}
                for did, base in raw_labels.items():
                    if label_counts[base] > 1:
                        suffix = did[-6:] if len(did) >= 6 else did
                        device_id_to_label[did] = f"{base} ({suffix})"
                    else:
                        device_id_to_label[did] = base
                return device_wifi_id_dict, device_id_to_label
            else:
                return None

    async def get_all_devices(self, access_token, home_id, refresh_token):
        """Return all supported devices (空调 and 冰箱) with type info."""
        timestamp = self.get_timestamp()
        url = 'https://api-wg.hismarttv.com/wg/dm/getHomeDeviceList'
        headers = {
            'Host': 'api-wg.hismarttv.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'User-Agent': 'okhttp/4.10.0',
        }
        params = {
            'sign': '',
            'languageId': '0',
            'version': '8.0',
            'accessToken': access_token,
            'homeId': home_id,
            'timezone': '28800',
            'format': '1',
            'timeStamp': str(timestamp),
        }
        async with self.session.get(url, headers=headers, params=params) as response:
            result = await response.json()
            if not isinstance(result, dict):
                return None
            response_obj = result.get("response")
            if not isinstance(response_obj, dict) or response_obj.get("resultCode") != 0:
                return None
            device_list = response_obj.get("deviceList")
            if not isinstance(device_list, list):
                return None
            devices = {}
            raw_labels = {}
            for device in device_list:
                if not isinstance(device, dict):
                    continue
                device_type_name = device.get("deviceTypeName")
                device_type = _device_type_from_name(device_type_name)
                did = device.get("deviceId")
                wifi_id = device.get("wifiId")
                if (
                    device_type is None
                    or not isinstance(did, str)
                    or not did
                    or not isinstance(wifi_id, str)
                    or not wifi_id
                ):
                    continue
                label = _device_select_label(device, did)
                raw_labels[did] = label
                devices[did] = {
                    "device_id": did,
                    "wifi_id": wifi_id,
                    "refresh_token": refresh_token,
                    "device_type": device_type,
                    "device_type_name": device_type_name,
                    "device_name": _device_text(device.get("deviceName")),
                    "device_code": _device_text(device.get("deviceCode")),
                    "label": label,
                }
                    
            label_counts = Counter(raw_labels.values())
            for did, base in raw_labels.items():
                if label_counts[base] > 1:
                    suffix = did[-6:] if len(did) >= 6 else did
                    devices[did]["label"] = f"{base} ({suffix})"
                
            return devices


class HiSenseAC:
    def __init__(self, wifi_id, device_id, refresh_token, session, device_name="", entity_name=""):
        self.wifi_id = wifi_id
        self.device_id = device_id
        self.refresh_token = refresh_token
        self.access_token = None
        self.session = session
        self.device_name = device_name
        self.entity_name = entity_name
        app_name_encoding = "%E6%B5%B7%E4%BF%A1%E6%99%BA%E6%85%A7%E5%AE%B6"
        # app_name = "海信智慧家"
        # app_name_encoding = urllib.parse.quote(app_name)
        self.headers = {
            'Host': 'api-wg.hismarttv.com',
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': f"{app_name_encoding}/4 CFNetwork/1492.0.1 Darwin/23.3.0",
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        self.refresh_headers = {
            'Host': 'bas-wg.hismarttv.com',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': f"{app_name_encoding}/4 CFNetwork/1492.0.1 Darwin/23.3.0",
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        self.url_head = "https://api-wg.hismarttv.com/agw/dsg/outer"
        self.power_url = f"{self.url_head}/sendDeviceModelCmd?accessToken="
        self.command_url = f"{self.url_head}/uploadRemoteLogicCmd?accessToken="
        self.check_url = f"{self.url_head}/getDeviceLogicalStatusArray?accessToken="
        self.refresh_url = "https://bas-wg.hismarttv.com/aaa/refresh_token2"
        self.power_data_template = {
            "wifiId": wifi_id,
            "deviceId": device_id,
            "extendParam": "1",
            "cmdVersion": "0",
        }
        self.check_data_template = {
            "deviceList": [
                {
                    "wifiId": wifi_id,
                    "deviceId": device_id,
                }
            ]
        }
        self.command_data_template = {
            "wifiId": wifi_id,
            "deviceId": device_id,
            "extendParm": "1",
            "cmdVersion": "1684085201",
        }
        self.status = {
            "power_on": False,
        }
        self.hvac_mode_lookup = {
            0: "FAN_ONLY",
            1: "HEAT",
            2: "COOL",
            3: "DRY",
            4: "AUTO",
        }
        self.fan_mode_lookup = {
            0: "AUTO",
            1: "DIFFUSE",
            2: "LOW",
            3: "MEDIUM",
            4: "HIGH",
        }
        self.climate_min_temp = 16
        self.climate_max_temp = 32

    async def _send_command(self, url, command_data, status_required=True):
        post_url = f"{url}{self.access_token}"
        try:
            async with self.session.post(
                post_url,
                headers=self.headers,
                json=command_data,
            ) as response:
                result = await response.json()
        except Exception:
            _LOGGER.error("Hisense request failed", exc_info=True)
            return False

        if not isinstance(result, dict):
            _LOGGER.error("Hisense response is not an object: %s", result)
            return False

        response_obj = result.get("response")
        if not isinstance(response_obj, dict):
            _LOGGER.error("Hisense response missing response object: %s", result)
            return False

        result_code = response_obj.get("resultCode")
        if result_code != 0:
            _LOGGER.warning("Hisense request failed with resultCode=%s", result_code)
            return False

        if not status_required:
            try:
                self._extract_status_payload(result)
            except ValueError:
                _LOGGER.debug("Hisense response accepted without status payload")
                return None

        if self._update_status_from_result(result):
            return True

        if not status_required:
            return None

        _LOGGER.error("Hisense response did not include a usable status payload")
        return False

    async def _robust_send_command(self, url, command_data, status_required=True):
        result = await self._send_command(url, command_data, status_required)
        if result is not False:
            return result
        _LOGGER.info("Attempting to refresh token and retry command")
        if not await self.refresh():
            _LOGGER.error("Failed to refresh token")
            return False
        return await self._send_command(url, command_data, status_required)

    def _extract_status_payload(self, result):
        if not isinstance(result, dict):
            raise ValueError("response is not an object")
        response = result.get("response")
        if not isinstance(response, dict):
            raise ValueError("missing response object")

        pre_status = response.get("preStatus")
        if isinstance(pre_status, str) and pre_status:
            return pre_status

        status_list = response.get("deviceStatusList")
        if isinstance(status_list, list) and status_list:
            first_status = status_list[0]
            if isinstance(first_status, dict):
                device_status = first_status.get("deviceStatus")
                if isinstance(device_status, str) and device_status:
                    return device_status

        raise ValueError("missing status payload")

    def _update_status_from_result(self, result):
        try:
            result_list_str = self._extract_status_payload(result)
            result_list = [int(i.strip()) for i in result_list_str.split(",")]
            if len(result_list) < _MIN_STATUS_VALUES:
                raise ValueError(
                    f"status payload has {len(result_list)} values, "
                    f"expected at least {_MIN_STATUS_VALUES}"
                )

            fan_mode_id = result_list[0]
            hvac_mode_id = result_list[4]
            swing_mode_id = result_list[209]
            if fan_mode_id not in self.fan_mode_lookup:
                raise ValueError(f"unknown fan mode id {fan_mode_id}")
            if hvac_mode_id not in self.hvac_mode_lookup:
                raise ValueError(f"unknown hvac mode id {hvac_mode_id}")
            if swing_mode_id not in _STATUS_SWING_MODES:
                raise ValueError(f"unknown swing mode id {swing_mode_id}")

            status = {
                "desired_temperature": result_list[9],
                "indoor_temperature": result_list[10],
                "hvac_mode_id": hvac_mode_id,
                "hvac_mode": self.hvac_mode_lookup[hvac_mode_id],
                "fan_mode_id": fan_mode_id,
                "fan_mode": self.fan_mode_lookup[fan_mode_id],
                "screen_on": result_list[58] == 1,
                "power_on": result_list[5] == 1,
                "aux_heat": result_list[45] == 1,
                "nature_wind": result_list[44] == 1,
                "swing_mode_id": swing_mode_id,
            }
        except (IndexError, TypeError, ValueError):
            _LOGGER.error("Failed to parse Hisense status response", exc_info=True)
            return False

        self.status.update(status)
        return True

    async def _send_command_and_update_status(self, url, command_data):
        result = await self._robust_send_command(
            url,
            command_data,
            status_required=False,
        )
        if result is True:
            return True
        if result is None:
            return bool(await self.check_status())
        return False

    async def turn_on(self):
        command_data = deepcopy(self.power_data_template)
        command_data["attributes"] = "{\"onAndOff\":\"On\"}"
        return await self._send_command_and_update_status(self.power_url, command_data)

    async def turn_off(self):
        command_data = deepcopy(self.power_data_template)
        command_data["attributes"] = "{\"onAndOff\":\"Off\"}"
        return await self._send_command_and_update_status(self.power_url, command_data)

    async def send_logic_command(self, id: int, param: int):
        command_data = deepcopy(self.command_data_template)
        command_data["cmdList"] = [
            {"cmdId": id, "cmdOrder": 0, "cmdParm": param, "delayTime": 0}
        ]
        return await self._send_command_and_update_status(self.command_url, command_data)

    async def check_status(self):
        if await self._robust_send_command(self.check_url, self.check_data_template):
            return self.get_status()
        return None

    def get_status(self):
        return dict(self.status)

    async def refresh(self):
        refresh_data = {
            'refreshToken': self.refresh_token,
            'appKey': "1234567890",
            'format': '1',
        }
        try:
            async with self.session.post(self.refresh_url,
                                         headers=self.refresh_headers,
                                         data=refresh_data) as response:
                result = await response.json()
                if not isinstance(result, list) or not result:
                    _LOGGER.error("Hisense token refresh returned unexpected body: %s", result)
                    return False
                token = result[0].get("token") if isinstance(result[0], dict) else None
                if not token:
                    _LOGGER.error("Hisense token refresh response did not include token")
                    return False
                self.access_token = token
                _LOGGER.debug(f"Get access token: {self.access_token}")
                return True
        except Exception:
            _LOGGER.error("Failed to refresh token", exc_info=True)
            return False


class HiSenseFridge:
    def __init__(self, wifi_id, device_id, refresh_token, session, device_name="", entity_name=""):
        self.wifi_id = wifi_id
        self.device_id = device_id
        self.refresh_token = refresh_token
        self.access_token = None
        self.session = session
        self.device_name = device_name
        self.entity_name = entity_name
        app_name_encoding = "%E6%B5%B7%E4%BF%A1%E6%99%BA%E6%85%A7%E5%AE%B6"
        self.headers = {
            'Host': 'api-wg.hismarttv.com',
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': f"{app_name_encoding}/4 CFNetwork/1492.0.1 Darwin/23.3.0",
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        self.refresh_headers = {
            'Host': 'bas-wg.hismarttv.com',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': f"{app_name_encoding}/4 CFNetwork/1492.0.1 Darwin/23.3.0",
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        self.url_head = "https://api-wg.hismarttv.com/agw/dsg/outer"
        self.power_url = f"{self.url_head}/sendDeviceModelCmd?accessToken="
        self.command_url = f"{self.url_head}/uploadRemoteLogicCmd?accessToken="
        self.check_url = f"{self.url_head}/getDeviceLogicalStatusArray?accessToken="
        self.refresh_url = "https://bas-wg.hismarttv.com/aaa/refresh_token2"
        self.power_data_template = {
            "wifiId": wifi_id,
            "deviceId": device_id,
            "extendParam": "1",
            "cmdVersion": "0",
        }
        self.check_data_template = {
            "deviceList": [
                {
                    "wifiId": wifi_id,
                    "deviceId": device_id,
                }
            ]
        }
        self.command_data_template = {
            "wifiId": wifi_id,
            "deviceId": device_id,
            "extendParm": "1",
            "cmdVersion": "1684085201",
        }
        self.status = {
            "power_on": False,
            "refrigerator_set_temperature": 5,
            "freeze_set_temperature": -18,
            "refrigerator_real_temperature": 5,
            "freeze_real_temperature": -18,
            "variation_real_temperature": 0,
            "ambient_temperature": 25,
            "work_mode_id": 0,
            "work_mode": "自定义",
            "variation_mode_id": 0,
            "variation_mode": "NORMAL",
        }
        self.work_mode_lookup = {
            0: "自定义",
            64: "智能",
            65: "速冷",
        }
        self.variation_mode_lookup = {
            16: "原鲜",
            32: "0℃养鲜",
            64: "母婴",
        }

    async def _send_command(self, url, command_data, status_required=True):
        post_url = f"{url}{self.access_token}"
        try:
            async with self.session.post(
                post_url,
                headers=self.headers,
                json=command_data,
            ) as response:
                result = await response.json()
        except Exception:
            _LOGGER.error("Hisense fridge request failed", exc_info=True)
            return False

        if not isinstance(result, dict):
            _LOGGER.error("Hisense fridge response is not an object: %s", result)
            return False

        response_obj = result.get("response")
        if not isinstance(response_obj, dict):
            _LOGGER.error("Hisense fridge response missing response object: %s", result)
            return False

        result_code = response_obj.get("resultCode")
        if result_code != 0:
            _LOGGER.warning("Hisense fridge request failed with resultCode=%s", result_code)
            return False

        if not status_required:
            try:
                self._extract_status_payload(result)
            except ValueError:
                _LOGGER.debug("Hisense fridge response accepted without status payload")
                return None

        if self._update_status_from_result(result):
            return True

        if not status_required:
            return None

        _LOGGER.error("Hisense fridge response did not include a usable status payload")
        return False

    async def _robust_send_command(self, url, command_data, status_required=True):
        result = await self._send_command(url, command_data, status_required)
        if result is not False:
            return result
        _LOGGER.info("Attempting to refresh token and retry fridge command")
        if not await self.refresh():
            _LOGGER.error("Failed to refresh fridge token")
            return False
        return await self._send_command(url, command_data, status_required)

    def _extract_status_payload(self, result):
        if not isinstance(result, dict):
            raise ValueError("response is not an object")
        response = result.get("response")
        if not isinstance(response, dict):
            raise ValueError("missing response object")

        pre_status = response.get("preStatus")
        if isinstance(pre_status, str) and pre_status:
            return pre_status

        status_list = response.get("deviceStatusList")
        if isinstance(status_list, list) and status_list:
            first_status = status_list[0]
            if isinstance(first_status, dict):
                device_status = first_status.get("deviceStatus")
                if isinstance(device_status, str) and device_status:
                    return device_status

        raise ValueError("missing status payload")

    def _update_status_from_result(self, result):
        try:
            result_list_str = self._extract_status_payload(result)
            result_list = [int(i.strip()) for i in result_list_str.split(",")]
            if len(result_list) < _MIN_FRIDGE_STATUS_VALUES:
                raise ValueError(
                    f"status payload has {len(result_list)} values, "
                    f"expected at least {_MIN_FRIDGE_STATUS_VALUES}"
                )

            work_mode_id = result_list[3]
            variation_mode_id = result_list[130] if len(result_list) > 130 else 0

            status = {
                "refrigerator_set_temperature": result_list[0],
                "freeze_set_temperature": result_list[1],
                "work_mode_id": work_mode_id,
                "work_mode": self.work_mode_lookup.get(work_mode_id, "自定义"),
                "power_on": result_list[4] == 1,
                "refrigerator_real_temperature": result_list[6],
                "freeze_real_temperature": result_list[7],
                "variation_real_temperature": result_list[8],
                "ambient_temperature": result_list[9],
                "variation_mode_id": variation_mode_id,
                "variation_mode": self.variation_mode_lookup.get(variation_mode_id, "NORMAL"),
            }
        except (IndexError, TypeError, ValueError):
            _LOGGER.error("Failed to parse Hisense fridge status response", exc_info=True)
            return False

        self.status.update(status)
        return True

    async def _send_command_and_update_status(self, url, command_data):
        result = await self._robust_send_command(
            url,
            command_data,
            status_required=False,
        )
        if result is True:
            return True
        if result is None:
            return bool(await self.check_status())
        return False

    async def turn_on(self):
        command_data = deepcopy(self.power_data_template)
        command_data["attributes"] = "{\"onAndOff\":\"On\"}"
        return await self._send_command_and_update_status(self.power_url, command_data)

    async def turn_off(self):
        command_data = deepcopy(self.power_data_template)
        command_data["attributes"] = "{\"onAndOff\":\"Off\"}"
        return await self._send_command_and_update_status(self.power_url, command_data)

    async def send_logic_command(self, id: int, param: int):
        command_data = deepcopy(self.command_data_template)
        command_data["cmdList"] = [
            {"cmdId": id, "cmdOrder": 0, "cmdParm": param, "delayTime": 0}
        ]
        return await self._send_command_and_update_status(self.command_url, command_data)

    async def set_refrigerator_temperature(self, temperature: int):
        return await self.send_logic_command(1, temperature)

    async def set_freeze_temperature(self, temperature: int):
        return await self.send_logic_command(2, temperature)

    async def set_work_mode(self, mode_id: int):
        return await self.send_logic_command(3, mode_id)

    async def set_fridge_mode(self, mode_id: int):
        if mode_id == 64:
            return await self.send_logic_command(19, 1)
        if mode_id == 65:
            return await self.send_logic_command(25, 1)
        return False

    async def set_variation_mode(self, mode_id: int):
        if mode_id == 64:
            return await self.send_logic_command(33, 1)
        if mode_id == 32:
            return await self.send_logic_command(34, 1)
        if mode_id == 16:
            return await self.send_logic_command(35, 1)
        return False

    async def check_status(self):
        if await self._robust_send_command(self.check_url, self.check_data_template):
            return self.get_status()
        return None

    def get_status(self):
        return dict(self.status)

    async def refresh(self):
        refresh_data = {
            'refreshToken': self.refresh_token,
            'appKey': "1234567890",
            'format': '1',
        }
        try:
            async with self.session.post(self.refresh_url,
                                         headers=self.refresh_headers,
                                         data=refresh_data) as response:
                result = await response.json()
                if not isinstance(result, list) or not result:
                    _LOGGER.error("Hisense fridge token refresh returned unexpected body: %s", result)
                    return False
                token = result[0].get("token") if isinstance(result[0], dict) else None
                if not token:
                    _LOGGER.error("Hisense fridge token refresh response did not include token")
                    return False
                self.access_token = token
                _LOGGER.debug(f"Get fridge access token: {self.access_token}")
                return True
        except Exception:
            _LOGGER.error("Failed to refresh fridge token", exc_info=True)
            return False
