# Curtain 3 Touch-to-Open command verification

Status: **not verified; no setter implemented**.

The published [Curtain 3 BLE specification](https://github.com/OpenWonderLabs/SwitchBotAPI-BLE/blob/latest/devicetypes/curtain3.md)
describes Touch-to-Open readback but does not document the setting command.
Do not infer a write command by changing a read opcode, and do not try guessed
configuration writes against a device.

## Capture procedure

Use an app-side Bluetooth HCI log or a BLE sniffer capable of capturing the
app's GATT writes and the curtain's notifications. PySwitchbot logging records
its own exchanges; it cannot capture commands sent by the SwitchBot app.

1. Record app version, phone OS, both curtain firmware versions, and whether
   the motors are paired. Assign anonymized device labels A and B and record
   which device is the chain head. Record the initial setting for both motors.
2. Capture a baseline app session that reads settings without changing them.
3. Capture enabling Touch-to-Open, then disabling it, then enabling it again.
   Record the target device, exact write bytes, notification bytes, and order.
   Repeat with the other motor selected in the app if the app permits that.
4. Read back the setting after each toggle. Record whether one motor or the
   entire chain changed, and verify behaviour by gently pulling the curtain.
5. Compare the writes with a separately captured change to another available
   setting, restoring its original value afterwards. Determine whether the
   command carries only Touch-to-Open or a shared configuration byte.
6. Close the app's connection before reading through PySwitchbot. Read basic,
   chain, summary, and advanced pages and retain complete replies. The read
   requests are `5702`, `570f468101`, `570f460401`, and `570f460402`.
7. Restore the original settings and verify normal/silent movement, stop,
   travel limits, direction, pairing, and schedules are unchanged.

Keep an extracted, anonymized sequence of the relevant GATT exchanges rather
than publishing a complete phone HCI log. Include timestamps and the response
status byte; retain the payload unchanged so tests can use actual device data.

## Evidence record

For each run, record:

- Capture identifier and date; app/OS versions; firmware for A and B.
- Pair topology and selected motor; initial settings and restored settings.
- GATT characteristic, direction (app write/device notification), exact hex
  payload, and timestamp for each relevant exchange.
- Touch-to-Open readback for both motors before and after the command.
- Observed command scope, acknowledgment, shared bits, and other state changes.
- Whether each transcript is a hardware capture or a synthetic test fixture.

Solar-equipped validation is separate. For charging diagnostics, another tester
must supply advanced-page replies for solar charging, solar full, and solar
connected without charging. Synthetic coverage is not hardware validation.
Never deliberately induce a device fault to generate a fixture.

## Setter acceptance gate

Implement the setter only when repeated captures establish the command bytes,
acknowledgment, addressing, and readback. If evidence is incomplete, keep the
read-only API and leave the setter unreleased.

The intended API is `await curtain.set_touch_to_open(enabled: bool) -> bool`.
It targets the connected motor unless captures prove chain-wide behaviour;
chain-wide behaviour must be documented before exposing the API.

If the command rewrites multiple settings, read fresh configuration and preserve
unrelated bits. Serialize the complete read/write/readback transaction using
existing transport locks without recursively acquiring the operation lock.
A successful acknowledgment alone is insufficient: return `True` only when
validated readback matches. Rejection or mismatch returns `False`; transport
errors propagate through existing exception types. Notify subscribers only
after updating confirmed cached observations.

Add tests using verified command fixtures for enable/disable, rejected replies,
readback mismatch, unrelated-bit preservation, both pair members, and concurrent
operations. Test the API on hardware before marking its PR ready for review.
