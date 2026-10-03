"""Library to handle connection with Switchbot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from bleak.backends.device import BLEDevice

from .const.curtain import CurtainChargingState


@dataclass
class SwitchBotAdvertisement:
    """Switchbot advertisement."""

    address: str
    data: dict[str, Any]
    device: BLEDevice
    rssi: int
    active: bool = False


@dataclass(frozen=True)
class CurtainMotorStatus:
    """Cached observations for a chain slot, not a persistent motor identity."""

    present: bool | None = None
    battery: int | None = None
    position: int | None = None
    solar_panel_present: bool | None = None
    charging_state: CurtainChargingState | None = None
    charging_state_raw: int | None = None
    touch_to_open: bool | None = None
    timestamps: Mapping[str, float] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamps", MappingProxyType(dict(self.timestamps)))
