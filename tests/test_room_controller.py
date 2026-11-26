from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from custom_components.hisense import _async_restore_room_controller_names
from custom_components.hisense.const import ROOM_CONTROLLER_MODEL, ROOM_CONTROLLER_TYPE
from custom_components.hisense.pyhisenseapi import (
    HiSenseLogin,
    HiSenseRoomController,
    _HiSenseDevice,
)
from custom_components.hisense.sensor import HisenseRoomTemperatureSensor


class RoomControllerTest(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_uses_nickname_and_exact_model(self):
        category = "connector.device.type.watersystem.central"
        devices = [
            {
                "deviceId": "sample-controller-a",
                "categoryCode": category,
                "product": {"code": ROOM_CONTROLLER_MODEL, "name": "Room controller"},
                "nickname": " Sample controller A ",
            },
            {
                "deviceId": "sample-controller-b",
                "categoryCode": category,
                "productCode": ROOM_CONTROLLER_MODEL,
                "product": {"name": "Room controller"},
                "nickname": " ",
            },
            {
                "deviceId": "sample-water-controller",
                "categoryCode": category,
                "productCode": "hitachiWaterTemperatureController",
            },
            {"deviceId": "sample-ac", "categoryCode": "aircondition"},
        ]
        reply = {"payload": {"status": "SUCCESS", "devices": devices}}
        with patch.object(_HiSenseDevice, "_post", new=AsyncMock(return_value=reply)):
            result = await HiSenseLogin(None).get_all_devices(
                "fixture-token", "fixture-home", None, "fixture-customer"
            )

        self.assertEqual(set(result), {"sample-controller-a", "sample-controller-b", "sample-ac"})
        self.assertEqual(result["sample-controller-a"]["label"], "Sample controller A")
        self.assertEqual(result["sample-controller-a"]["device_type"], ROOM_CONTROLLER_TYPE)
        self.assertEqual(result["sample-controller-b"]["label"], "Room controller")
        self.assertEqual(result["sample-ac"]["device_type"], "空调")

    async def test_duplicate_nicknames_keep_distinct_selection_labels(self):
        ids = ("sample-a-common", "sample-b-common")
        devices = [
            {
                "deviceId": device_id,
                "categoryCode": "connector.device.type.watersystem.central",
                "productCode": ROOM_CONTROLLER_MODEL,
                "nickname": "Repeated nickname",
            }
            for device_id in ids
        ]
        reply = {"payload": {"status": "SUCCESS", "devices": devices}}
        with patch.object(_HiSenseDevice, "_post", new=AsyncMock(return_value=reply)):
            result = await HiSenseLogin(None).get_all_devices(
                "fixture-token", "fixture-home", None, "fixture-customer"
            )

        self.assertEqual(len({device["label"] for device in result.values()}), 2)
        self.assertTrue(all(device["device_name"] == "Repeated nickname" for device in result.values()))

    async def test_temperature_sensor_uses_measured_value_and_clears_missing_value(self):
        client = HiSenseRoomController(
            "", "sample-controller", None, None, device_name="Sample controller"
        )
        coordinator = SimpleNamespace(device_type=ROOM_CONTROLLER_TYPE, client=client, data=None)
        sensor = HisenseRoomTemperatureSensor(coordinator)
        client._update_from_states({"setTemperature": 24, "realTemperature": "23.5"})
        self.assertEqual(sensor.native_value, 23.5)
        self.assertEqual(sensor.device_info["name"], "Sample controller")
        self.assertEqual(sensor.device_info["identifiers"], {("hisense", "sample-controller")})

        client._update_from_states({"realTemperature": "NaN", "indoorTemperature": 0})
        self.assertEqual(sensor.native_value, 0)
        client._update_from_states({"setTemperature": 24, "realTemperature": True})
        self.assertIsNone(sensor.native_value)

    async def test_backfill_preserves_identity_and_does_not_repeat(self):
        original = {
            "device_id": "sample-controller",
            "device_type": ROOM_CONTROLLER_TYPE,
            "home_id": "fixture-home",
            "customer_id": "fixture-customer",
            "access_token": "fixture-token",
            "device_name": "Room controller",
        }
        entry = SimpleNamespace(data={"devices": [original]})

        def update_entry(entry, *, data):
            entry.data = data

        hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=update_entry))
        discovered = {
            original["device_id"]: {
                "nickname": "Sample controller",
                "device_name": "Sample controller",
                "label": "Sample controller",
            }
        }
        with patch.object(
            HiSenseLogin, "get_all_devices", new=AsyncMock(return_value=discovered)
        ) as discover:
            await _async_restore_room_controller_names(hass, entry, None)
            await _async_restore_room_controller_names(hass, entry, None)

        discover.assert_awaited_once()
        updated, = entry.data["devices"]
        self.assertEqual(updated["nickname"], "Sample controller")
        self.assertEqual(updated["device_name"], "Sample controller")
        self.assertEqual(updated["device_id"], original["device_id"])
        self.assertEqual(updated["access_token"], original["access_token"])
