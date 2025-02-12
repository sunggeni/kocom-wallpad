"""Constants for py wallpad."""

import logging

_LOGGER = logging.getLogger(__package__)

HEADER = b"\xAA\x55"  # 0xAA 0x55
TAILER = b"\x0D\x0D"  # 0x0D 0x0D

POWER = "power"
BRIGHTNESS = "brightness"
LEVEL = "level"
AWAY = "away"
TARGET_TEMP = "target_temp"
CURRENT_TEMP = "current_temp"
STATE = "state"
HOTWATER = "hotwater"
HEATWATER = "heatwater"
TEMPERATURE = "temperature"
CODE = "code"
ERROR = "error"
OPER_MODE = "oper_mode"
FAN_MODE = "fan_mode"
VENT_MODE = "vent_mode"
FAN_SPEED = "fan_speed"
CO2 = "co2"
PM10 = "pm10"
PM25 = "pm25"
VOC = "voc"
HUMIDITY = "humidity"
TIME = "time"
DIRECTION = "direction"
FLOOR = "floor"
RING = "ring"
SHUTDOWN = "shutdown"
ONCE = "once"
ALWAYS = "always"
