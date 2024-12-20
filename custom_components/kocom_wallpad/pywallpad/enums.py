"""Enums for py wallpad."""

from enum import Enum

class DeviceType(Enum):
    """Device types for Kocom devices."""
    WALLPAD = "01"
    LIGHT = "0e"
    GAS = "2c"
    DOORLOCK = "33"
    THERMOSTAT = "36"
    AC = "39"
    OUTLET = "3b"
    EV = "44"
    FAN = "48"
    MOTION = "60"
    IGNORE = "86"
    IAQ = "98"

class Command(Enum):
    """Commands for Kocom devices."""
    STATUS = "00"
    ON = "01"
    OFF = "02"
    DETECT = "04"
    SCAN = "3a"
    
class PacketType(Enum):
    """Packet types for Kocom devices."""
    SEND = "b"
    RECV = "d"
    
class OpMode(Enum):
    """Operating modes for AC devices."""
    COOL = "00"
    FAN_ONLY = "01"
    DRY = "02"
    AUTO = "03"

class FanMode(Enum):
    """Fan modes for fans."""
    OFF = "00"
    LOW = "01"
    MEDIUM = "02"
    HIGH = "03"

class VentMode(Enum):
    """Ventilation modes for fans."""
    OFF = "00"
    VENTILATION = "01"
    AUTO = "02"
    AIR_PURIFIER = "08"

class FanSpeed(Enum):
    """Fan speeds for fans."""
    OFF = "00"
    LOW = "40"
    MEDIUM = "80"
    HIGH = "c0"
    