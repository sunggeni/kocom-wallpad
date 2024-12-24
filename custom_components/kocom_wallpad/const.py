"""Constants for the Kocom Wallpad integration."""

from __future__ import annotations

from .pywallpad.packet import (
    LightPacket,
    OutletPacket,
    ThermostatPacket,
    AcPacket,
    FanPacket,
    IAQPacket,
    GasPacket,
    MotionPacket,
    EvPacket,
)

from homeassistant.const import Platform
import logging

DOMAIN = "kocom_wallpad"
LOGGER = logging.getLogger(__package__)

DEFAULT_PORT = 8899

BRAND_NAME = "kocom"
MANUFACTURER = "KOCOM Co., Ltd"
MODEL = "Smart Wallpad"
SW_VERSION = "1.0.2"

DEVICE_TYPE = "device_type"
ROOM_ID = "room_id"
SUB_ID = "sub_id"
PACKET = "packet"

PLATFORM_MAPPING: dict[type[KocomPacket], Platform] = { # type: ignore
    LightPacket: Platform.LIGHT,
    OutletPacket: Platform.SWITCH,
    ThermostatPacket: Platform.CLIMATE,
    AcPacket: Platform.CLIMATE,
    FanPacket: Platform.FAN,
    IAQPacket: Platform.SENSOR,
    GasPacket: Platform.SWITCH,
    MotionPacket: Platform.BINARY_SENSOR,
    EvPacket: Platform.SWITCH,
}
