from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from switchbot import CurtainChargingState, CurtainMotorStatus
from switchbot.devices.base_cover import COVER_EXT_ADV_KEY, COVER_EXT_SUM_KEY
from switchbot.devices.curtain import CURTAIN_EXT_CHAIN_INFO_KEY
from switchbot.devices.device import DEVICE_GET_BASIC_SETTINGS_KEY

from .test_curtain_diagnostics import BASIC, CHAIN, diagnostic_device


@pytest.mark.asyncio
async def test_zero_battery_and_zero_settings_are_a_present_motor():
    device, _ = diagnostic_device()
    assert await device.refresh_diagnostics()
    primary, secondary = device.motor_status.values()
    assert primary.battery == 80
    assert secondary.present is True
    assert secondary.battery == 0
    assert secondary.touch_to_open is False
    assert secondary.charging_state is CurtainChargingState.SOLAR_FULL
    assert secondary.charging_state_raw == 4
    assert secondary.solar_panel_present is False
    assert secondary.position == 60
    assert set(secondary.timestamps) == {"chain", "summary", "advanced"}
    assert device.get_battery_percent() == 80
    assert device.get_position() == 40
    assert device.ext_info_sum["device1"]["touchToOpen"] is False


@pytest.mark.asyncio
async def test_snapshots_are_immutable_and_do_not_perform_io():
    device, _ = diagnostic_device()
    assert await device.refresh_diagnostics()
    device._send_command.reset_mock()
    snapshot = device.motor_status
    with pytest.raises(TypeError):
        snapshot[0] = CurtainMotorStatus()
    with pytest.raises(FrozenInstanceError):
        snapshot[0].battery = 100
    with pytest.raises(TypeError):
        snapshot[0].timestamps["basic"] = 0
    device._send_command.assert_not_awaited()
    await device.refresh_diagnostics()
    assert snapshot[0] is not device.motor_status[0]


def test_unknown_before_observation():
    device, _ = diagnostic_device()
    assert device.motor_status[0] == CurtainMotorStatus()
    assert device.motor_status[1] == CurtainMotorStatus()


@pytest.mark.asyncio
async def test_pair_removed_and_added_again():
    device, replies = diagnostic_device()
    assert await device.refresh_diagnostics()
    old_snapshot = device.motor_status
    replies[DEVICE_GET_BASIC_SETTINGS_KEY] = bytes([1, 80, 10, 1, 0x40, 4, 40, 0])
    replies[CURTAIN_EXT_CHAIN_INFO_KEY] = bytes([1, 0, 0, 1, 40, 80, 0, 0])
    assert await device.refresh_diagnostics()
    assert device.motor_status[1] == CurtainMotorStatus(present=False)
    assert "device1" not in device.ext_info_sum
    assert "device1" not in device.ext_info_adv
    assert old_snapshot[1].present is True
    replies[DEVICE_GET_BASIC_SETTINGS_KEY] = BASIC
    replies[CURTAIN_EXT_CHAIN_INFO_KEY] = CHAIN
    assert await device.refresh_diagnostics()
    assert device.motor_status[1].present is True
    assert device.motor_status[1].battery == 0


@pytest.mark.asyncio
async def test_topology_disagreement_invalidates_secondary_until_coherent_refresh():
    device, replies = diagnostic_device()
    assert await device.refresh_diagnostics()
    replies[CURTAIN_EXT_CHAIN_INFO_KEY] = bytes([1, 0, 0, 1, 40, 80, 0, 0])
    assert not await device.refresh_diagnostics()
    assert device.motor_status[1] == CurtainMotorStatus()
    assert "device1" not in device.ext_info_sum
    assert "device1" not in device.ext_info_adv
    replies[CURTAIN_EXT_CHAIN_INFO_KEY] = CHAIN
    assert await device.refresh_diagnostics()
    assert device.motor_status[1].present is True


@pytest.mark.asyncio
async def test_page_failures_retain_values_and_freshness():
    device, replies = diagnostic_device()
    with patch("switchbot.devices.curtain.time.monotonic", return_value=100):
        assert await device.refresh_diagnostics()
    replies[COVER_EXT_ADV_KEY] = b"\x05"
    replies[COVER_EXT_SUM_KEY] = b"\x05"
    with patch("switchbot.devices.curtain.time.monotonic", return_value=200):
        assert not await device.refresh_diagnostics()
    status = device.motor_status[1]
    assert status.battery == 0
    assert status.touch_to_open is False
    assert dict(status.timestamps) == {"chain": 200, "summary": 100, "advanced": 100}


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [True, False])
async def test_chain_flags_and_orientation(reverse):
    device, replies = diagnostic_device(reverse)
    replies[CURTAIN_EXT_CHAIN_INFO_KEY] = bytes(
        [1, 0, 0, 2, 40, 80, 0x80 | 60, 0x80 | 50]
    )
    assert await device.refresh_diagnostics()
    status = device.motor_status[1]
    assert status.position == (40 if reverse else 60)
    assert status.solar_panel_present is True
    assert device._chain_info["device1"]["charging"] is True


@pytest.mark.asyncio
async def test_newer_chain_battery_takes_precedence_over_old_advanced_page():
    device, replies = diagnostic_device()
    with patch("switchbot.devices.curtain.time.monotonic", return_value=100):
        assert await device.refresh_diagnostics()
    replies[CURTAIN_EXT_CHAIN_INFO_KEY] = bytes([1, 0, 0, 2, 40, 80, 60, 30])
    with patch("switchbot.devices.curtain.time.monotonic", return_value=200):
        await device.get_extended_chain_info()
    assert device.motor_status[1].battery == 30
    assert device.motor_status[1].timestamps["advanced"] == 100


@pytest.mark.asyncio
async def test_invalid_percentages_are_unknown():
    device, replies = diagnostic_device()
    replies[CURTAIN_EXT_CHAIN_INFO_KEY] = bytes([1, 0, 0, 2, 127, 127, 127, 127])
    replies[COVER_EXT_ADV_KEY] = bytes([1, 255, 10, 255, 255, 10, 255])
    assert await device.refresh_diagnostics()
    assert device.motor_status[1].battery is None
    assert device.motor_status[1].position is None
    assert device.motor_status[1].charging_state is None


def test_timestamp_mapping_is_defensively_copied():
    timestamps = {"chain": 100}
    status = CurtainMotorStatus(present=True, timestamps=timestamps)
    timestamps["chain"] = 200
    assert status.timestamps["chain"] == 100


@pytest.mark.asyncio
async def test_basic_settings_do_not_establish_presence_without_chain_response():
    device, replies = diagnostic_device()
    replies[CURTAIN_EXT_CHAIN_INFO_KEY] = b"\x05"
    assert not await device.refresh_diagnostics()
    assert device.motor_status[0] == CurtainMotorStatus()
    assert device.motor_status[1] == CurtainMotorStatus()
