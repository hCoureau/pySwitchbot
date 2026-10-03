from unittest.mock import Mock

import pytest

from switchbot.devices.device import DEVICE_GET_BASIC_SETTINGS_KEY

from .test_curtain_diagnostics import diagnostic_device


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flags", "state", "fault", "touch", "solar"),
    [
        (0, 0, False, False, False),
        (0x08, 0, True, False, False),
        (0x40, 0, False, True, False),
        (0, 0x08, False, False, True),
        (0x48, 0x08, True, True, True),
        (0xB7, 0xF4, False, False, False),
    ],
)
async def test_independent_flags(flags, state, fault, touch, solar):
    device, replies = diagnostic_device()
    replies[DEVICE_GET_BASIC_SETTINGS_KEY] = bytes([1, 80, 10, 2, flags, state, 40, 0])
    await device.get_extended_chain_info()
    await device.update()
    device._send_command.reset_mock()
    assert device.get_fault() is fault
    assert device.get_touch_to_open() is touch
    assert device.get_solar_panel_present() is solar
    assert device.motor_status[0].touch_to_open is touch
    assert device.motor_status[0].solar_panel_present is solar
    device._send_command.assert_not_awaited()


def test_unknown_flags_before_a_validated_reply():
    device, _ = diagnostic_device()
    device.parsed_data.update(fault=True, touchToOpen=True, solarPanel=True)
    assert device.get_fault() is None
    assert device.get_touch_to_open() is None
    assert device.get_solar_panel_present() is None
    device._send_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_read_retains_valid_flags_and_timestamp():
    device, replies = diagnostic_device()
    replies[DEVICE_GET_BASIC_SETTINGS_KEY] = bytes([1, 80, 10, 2, 0x48, 0x08, 40, 0])
    await device.update()
    timestamp = device.diagnostic_timestamps["basic"]
    replies[DEVICE_GET_BASIC_SETTINGS_KEY] = b"\x05"
    await device.update()
    assert device.get_fault() is True
    assert device.get_touch_to_open() is True
    assert device.get_solar_panel_present() is True
    assert device.diagnostic_timestamps["basic"] == timestamp


@pytest.mark.asyncio
async def test_subscribers_observe_confirmed_flag_changes():
    device, replies = diagnostic_device()
    callback = Mock()
    device.subscribe(callback)
    await device.update()
    assert device.get_fault() is False
    replies[DEVICE_GET_BASIC_SETTINGS_KEY] = bytes([1, 80, 10, 2, 0x08, 4, 40, 0])
    await device.update()
    assert device.get_fault() is True
    assert device.get_touch_to_open() is False
    assert callback.call_count == 2
