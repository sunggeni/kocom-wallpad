"""Constants for py wallpad."""

import logging

_LOGGER = logging.getLogger(__package__)

PREFIX_HEADER = b"\xaaU"
SUFFIX_HEADER = b"\r\r"

POWER = "power"
BRIGHTNESS = "brightness"
LEVEL = "level"

AWAY_MODE = "away_mode"
TARGET_TEMP = "target_temp"
CURRENT_TEMP = "current_temp"
STATE = "state"
ERROR_CODE = "error_code"
HOTWATER_TEMP = "hotwater_temp"
HEATWATER_TEMP = "heatwater_temp"

OP_MODE = "op_mode"
FAN_MODE = "fan_mode"

VENT_MODE = "vent_mode"
FAN_SPEED = "fan_speed"
PRESET_LIST = "preset_list"
SPEED_LIST = "speed_list"

PM10 = "pm10"
PM25 = "pm25"
CO2 = "co2"
VOC = "voc"
TEMPERATURE = "temperature"
HUMIDITY = "humidity"

TIME = "time"
DATE = "date"
