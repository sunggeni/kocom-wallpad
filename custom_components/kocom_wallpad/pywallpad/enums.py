"""Enums for py wallpad."""

from enum import IntEnum, StrEnum

class PacketType(IntEnum):
    """Packet types for Kocom devices."""
    SEND = 0x0B
    RECV = 0x0D

class DeviceType(IntEnum):
    """Device types for Kocom devices."""
    WALLPAD = 0x01
    LIGHT = 0x0E
    GAS = 0x2C
    THERMOSTAT = 0x36
    AC = 0x39
    OUTLET = 0x3B
    EV = 0x44
    VENT = 0x48
    MOTION = 0x60
    IAQ = 0x98

class Command(IntEnum):
    """Commands for Kocom devices."""
    STATUS = 0x00
    ON = 0x01
    OFF = 0x02
    DETECT = 0x04
    SCAN = 0x3A

class DoorPhoneCommand(IntEnum):
    """Door phone commands."""
    INVOKE = 0x09
    CONTROL = 0x0B

class DoorPhoneEntrance(StrEnum):
    """Door phone entrance types."""
    PRIVATE = "private"
    PUBLIC = "public"

class DoorPhoneEventType(IntEnum):
    """Door phone event types."""
    RING = 0x01    # 현관 벨 울림
    PICKUP = 0x02  # 수화기 들기 or 응답
    CALL = 0x03    # 통화
    EXIT = 0x04    # 통화 종료
    OPEN = 0x24    # 문 개방