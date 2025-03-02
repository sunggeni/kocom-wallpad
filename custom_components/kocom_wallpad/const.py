"""Constants for the Kocom Wallpad integration."""

from __future__ import annotations

from .pywallpad.packet import (
    KocomPacket,
    ThermostatPacket,
    VentPacket,
    IAQPacket,
    GasPacket,
    MotionPacket,
    EVPacket,
    DoorPhonePacket,
)

from homeassistant.const import Platform
import logging

DOMAIN = "kocom_wallpad"
LOGGER = logging.getLogger(__package__)

DEFAULT_PORT = 8899

BRAND_NAME = "Kocom"
MANUFACTURER = "KOCOM Co., Ltd"
MODEL = "Smart Wallpad"
SW_VERSION = "1.1.8"

DEVICE_TYPE = "device_type"
ROOM_ID = "room_id"
SUB_ID = "sub_id"

PACKET_DATA = "packet_data"
LAST_DATA = "last_data"

PLATFORM_MAPPING: dict[type[KocomPacket], Platform] = {
    ThermostatPacket: Platform.CLIMATE,
    VentPacket: Platform.FAN,
    IAQPacket: Platform.SENSOR,
    MotionPacket: Platform.BINARY_SENSOR,
    EVPacket: Platform.SWITCH,
    DoorPhonePacket: Platform.SWITCH,
}

PLATFORM_PACKET_TYPE: tuple[type[KocomPacket], ...] = (
    ThermostatPacket,
    VentPacket,
    EVPacket,
    DoorPhonePacket,
)
