"""Standalone tests for Hisense 00f washer protocol support."""

import asyncio
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "hisense"
    / "pyhisenseapi.py"
)
SPEC = importlib.util.spec_from_file_location("pyhisenseapi", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def washer_result(values):
    return {
        "response": {
            "deviceStatusList": [
                {"deviceStatus": ",".join(map(str, values))}
            ]
        }
    }


def test_washer_device_type_detection():
    assert MODULE._device_type_from_name("滚筒洗衣机") == "洗衣机"
    assert MODULE._device_type_from_name("洗衣干衣机") == "洗衣机"
    assert MODULE._device_type_from_name("智能空调") == "空调"
    assert MODULE._device_type_from_name("对开门冰箱") == "冰箱"


def test_washer_support_is_restricted_to_verified_00f_or_e3s_family():
    assert MODULE._is_supported_00f_washer({"deviceType": "00f"})
    assert MODULE._is_supported_00f_washer({"deviceCode": "WH120E3S"})
    assert not MODULE._is_supported_00f_washer({"deviceCode": "OTHER123"})


def test_device_classification_requires_washer_identity_and_verified_family():
    assert (
        MODULE._device_type(
            {"deviceTypeName": "滚筒洗衣机", "deviceType": "00f"}
        )
        == "洗衣机"
    )
    assert MODULE._device_type({"deviceTypeName": "滚筒洗衣机"}) is None
    assert MODULE._device_type({"deviceType": "00f"}) is None
    assert MODULE._device_type({"deviceTypeName": "智能空调"}) == "空调"
    assert MODULE._device_type({"deviceTypeName": "对开门冰箱"}) == "冰箱"


def test_washer_status_snapshot_and_diff():
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)
    first_values = [0] * 101
    first_values[1] = 1
    first_values[3] = 7
    second_values = first_values.copy()
    second_values[1] = 2

    assert client._update_status_from_result(washer_result(first_values))
    assert client.get_status()["protocol_payload_length"] == 101
    assert client.get_status()["protocol_nonzero_values"] == {"1": 1, "3": 7}
    assert client.get_status()["protocol_changed_indices"] == []

    assert client._update_status_from_result(washer_result(second_values))
    assert client.get_status()["protocol_changed_indices"] == [1]
    assert len(client.get_status()["protocol_payload_sha256"]) == 64


def test_washer_aihome_payload_shape_is_supported():
    values = [0] * 101
    values[9] = 1
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)

    assert client._update_status_from_result(
        {
            "payload": {
                "status": "SUCCESS",
                "deviceStatus": ",".join(map(str, values)),
            }
        }
    )
    assert client.get_status()["power_on"] is True


@pytest.mark.parametrize(
    "result_factory",
    [
        lambda values: {
            "payload": {
                "status": "SUCCESS",
                "deviceStatus": ",".join(map(str, values)),
            }
        },
        washer_result,
    ],
)
def test_washer_check_status_accepts_successful_response_shapes(
    monkeypatch, result_factory
):
    values = [0] * 101
    values[9] = 1
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)

    async def refresh():
        return True

    async def post(*args, **kwargs):
        return result_factory(values)

    monkeypatch.setattr(client, "refresh", refresh)
    monkeypatch.setattr(client, "_post", post)

    status = asyncio.run(client.check_status())
    assert status is not None
    assert status["power_on"] is True


def test_washer_check_status_rejects_explicit_failure(monkeypatch):
    values = [0] * 101
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)
    baseline = client.get_status()

    async def refresh():
        return True

    async def post(*args, **kwargs):
        result = washer_result(values)
        result["payload"] = {"status": "FAILURE"}
        return result

    monkeypatch.setattr(client, "refresh", refresh)
    monkeypatch.setattr(client, "_post", post)

    assert asyncio.run(client.check_status()) is None
    assert client.get_status() == baseline


def test_washer_snapshot_is_a_copy():
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)
    values = [0] * 101
    values[0] = 1
    client._update_status_from_result(washer_result(values))
    snapshot = client.get_status()
    snapshot["protocol_raw_values"][0] = 99
    assert client.get_status()["protocol_raw_values"] == values


def test_washer_cylinder_fields_use_zero_based_apk_lut():
    raw = [0] * 106
    raw[6] = 1
    raw[8] = 1
    raw[9] = 1
    raw[11] = 8
    raw[12] = 35
    raw[13], raw[14] = 3, 32
    raw[15] = 42
    raw[27] = 7
    raw[28], raw[29] = 1, 44
    raw[37] = 12
    raw[38] = 6
    raw[80] = 2
    raw[100] = 1
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)

    assert client._update_status_from_result(washer_result(raw))
    status = client.get_status()
    assert status["run_state"] == 1
    assert status["power_on"] is True
    assert status["phase"] == 8
    assert status["phase_label"] == "烘干"
    assert status["program"] == 35
    assert status["remaining_minutes"] == 300
    assert status["gate_locked"] is True
    assert status["fault"] == 7
    assert status["motor_speed"] == 800
    assert status["temperature_raw"] == 42
    assert status["configured_spin"] == 1200
    assert status["configured_temperature"] == "60 °C"
    assert status["child_lock"] is True
    assert status["dry_setting"] == "熨烫"


def test_washer_preserves_all_verified_dry_setting_labels():
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)
    for setting, label in enumerate(
        (
            "关闭",
            "即穿",
            "熨烫",
            "存放",
            "定时烘 1 挡",
            "定时烘 2 挡",
            "定时烘 3 挡",
            "定时烘 4 挡",
            "定时烘 5 挡",
            "定时烘 6 挡",
        )
    ):
        raw = [0] * 101
        raw[80] = setting
        assert client._update_status_from_result(washer_result(raw))
        assert client.get_status()["dry_setting"] == label


def test_washer_short_payload_is_rejected_without_losing_state():
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)
    baseline = client.get_status()
    assert not client._update_status_from_result(washer_result([0, 1, 2]))
    assert client.get_status() == baseline


@pytest.mark.parametrize(
    ("phase", "label"),
    list(
        enumerate(
            (
                "待机",
                "预约等待",
                "浸泡",
                "预洗",
                "主洗",
                "漂洗",
                "脱水",
                "洗涤完成",
                "烘干",
                "风干",
                "晾护",
            )
        )
    ),
)
def test_washer_phase_labels(phase, label):
    assert MODULE.WASHER_PHASE_LABELS[phase] == label


def test_washer_machine_state_distinguishes_standby_pause_and_complete():
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)

    def update(run_state, phase):
        raw = [0] * 101
        raw[8], raw[9], raw[11], raw[29] = run_state, 1, phase, 10
        assert client._update_status_from_result(washer_result(raw))
        return client.get_status()["machine_state"]

    assert update(0, 0) == "待机"
    assert update(0, 4) == "暂停"
    assert update(0, 7) == "完成"


def test_washer_exposes_no_device_controls():
    client = MODULE.HiSenseWasher("wifi", "device", "refresh", None)
    assert not hasattr(client, "turn_on")
    assert not hasattr(client, "set_temperature")
    assert not hasattr(client, "set_prompt_sound")
