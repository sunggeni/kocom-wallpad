"""Packet class for py wallpad."""

from __future__ import annotations

from enum import IntEnum
from typing import Any, ClassVar
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime

from .const import (
    _LOGGER,
    POWER,
    BRIGHTNESS,
    LEVEL,
    AWAY,
    TARGET_TEMP,
    CURRENT_TEMP,
    STATE,
    HOTWATER,
    HEATWATER,
    TEMPERATURE,
    CODE,
    ERROR,
    OPER_MODE,
    FAN_MODE,
    VENT_MODE,
    FAN_SPEED,
    CO2,
    PM10,
    PM25,
    VOC,
    HUMIDITY,
    TIME,
    DIRECTION,
    FLOOR,
    RING,
    SHUTDOWN,
    ONCE,
    ALWAYS,
)
from .enums import (
    PacketType,
    DeviceType,
    Command,
    DoorPhoneCommand,
    DoorPhoneEntrance,
    DoorPhoneEventType,
)


@dataclass
class Device:
    """Device class for Kocom devices."""
    device_type: str
    device_id: str
    room_id: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    sub_id: str | None = None

    def __repr__(self) -> str:
        """Return a string representation of the device."""
        return f"Device(device_type={self.device_type}, device_id={self.device_id}, room_id={self.room_id}, state={self.state}, sub_id={self.sub_id})"
    

class KocomPacket:
    """Base class for Kocom packets."""

    def __init__(self, packet: bytes) -> None:
        """Initialize the packet."""
        self.packet = packet
        self.pt = packet[3] >> 4
        self.seq = packet[3] & 0x0F

        self.packet_type = PacketType(self.pt)
        self.sequence = self.seq
        self.dest = packet[5:7]
        self.src = packet[7:9]
        self.command = Command(packet[9])
        self.value = packet[10:18]
        self.checksum = packet[18]

        self._address = self.src
        self._device: Device = None
        self._last_data: dict[str, Any] = {}

    def __repr__(self) -> str:
        """Return a string representation of the packet."""
        return f"KocomPacket(packet_type={self.packet_type.name}, sequence={self.sequence:#x}, dest={self.dest.hex()}, src={self.src.hex()}, command={self.command.name}, value={self.value.hex()}, checksum={self.checksum:#x})"
    
    @property
    def device_type(self) -> DeviceType:
        """Return the device type."""
        if self._address[0] == DeviceType.WALLPAD.value:
            self._address = self.dest
        return DeviceType(self._address[0])
    
    @property
    def room_id(self) -> str:
        """Return the room ID."""
        return str(self._address[1])
    
    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return f"{self.device_name()}_{self.room_id}"
    
    def device_name(self, capital=False) -> str:
        """Return the device name."""
        if capital:
            return self.device_type.name.upper()
        return self.device_type.name.lower()
    
    def parse_data(self) -> list[Device]:
        """Parse data from the packet."""
        _LOGGER.warning("Parsing not implemented for %s", self.device_name())
        return []
    
    def make_packet(self, command: Command, value_packet: bytearray) -> bytearray:
        """Make a packet."""
        address_part = (
            bytearray([0x01, 0x00]) + bytearray(self._address) 
            if self.device_type == DeviceType.EV 
            else bytearray(self._address) + bytearray([0x01, 0x00])
        )
        return bytearray([0x30, 0xBC, 0x00]) + address_part + bytearray([command.value]) + value_packet


class LightPacket(KocomPacket):
    """Handles packets for light devices."""

    _class_last_data: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, packet: bytes) -> None:
        """Initialize the packet."""
        super().__init__(packet)
        if self.device_id not in self._class_last_data:
            self._class_last_data[self.device_id] = {
                "ids": [],
                "bri_lv": [],
            }
        self._last_data.update(self._class_last_data)

    def parse_data(self) -> list[Device]:
        """Parse light-specific data."""
        devices = []

        for i, value in enumerate(self.value[:8]):
            is_on = value == 0xFF
            brightness = value if not is_on else 0

            if is_on and i not in self._last_data[self.device_id]["ids"]:
                self._last_data[self.device_id]["ids"].append(i)
                self._last_data[self.device_id]["ids"].sort()
                _LOGGER.debug(
                    "New light discovered - Room: %s, Index: %s, Current indices: %s",
                    self.room_id, i, self._last_data[self.device_id]["ids"]
                )
            
            if (
                brightness > 0 and 
                i in self._last_data[self.device_id]["ids"] and
                brightness not in self._last_data[self.device_id]["bri_lv"]
            ):
                self._last_data[self.device_id]["bri_lv"].append(brightness)
                self._last_data[self.device_id]["bri_lv"].sort()
                _LOGGER.debug(
                    "New brightness level discovered - Room: %s, Index: %s, Level: %s, Current levels: %s",
                    self.room_id, i, brightness, self._last_data[self.device_id]["bri_lv"]
                )
            
            if i in self._last_data[self.device_id]["ids"]:
                state = {POWER: is_on}
                has_brightness = bool(self._last_data[self.device_id]["bri_lv"])

                if has_brightness:
                    state[POWER] = value > 0
                    state[BRIGHTNESS] = brightness
                    state[LEVEL] = self._last_data[self.device_id]["bri_lv"]
                
                device = Device(
                    device_type=self.device_name(),
                    room_id=self.room_id,
                    device_id=self.device_id,
                    state=state,
                    sub_id=str(i),
                )
                devices.append(device)
                
        return devices
    
    def make_scan(self) -> bytearray:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN, bytearray(8))
    
    def make_power_status(self, power: bool) -> bytearray:
        """Make a power status packet."""
        sub_id = int(self._device.sub_id)
        value = bytearray(self.value)
        value[sub_id] = 0xFF if power else 0x00
        return super().make_packet(Command.STATUS, value)
    
    def make_brightness_status(self, brightness: int) -> bytearray:
        """Make a brightness status packet."""
        sub_id = int(self._device.sub_id)
        value = bytearray(self.value)
        value[sub_id] = brightness
        return super().make_packet(Command.STATUS, value)


class OutletPacket(KocomPacket):
    """Handles packets for outlet devices."""

    _class_last_data: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, packet: bytes) -> None:
        """Initialize the packet."""
        super().__init__(packet)
        if self.device_id not in self._class_last_data:
            self._class_last_data[self.device_id] = {
                "ids": [],
            }
        self._last_data.update(self._class_last_data)

    def parse_data(self) -> list[Device]:
        """Parse outlet-specific data."""
        devices = []
        
        for i, value in enumerate(self.value[:8]):
            is_on = value == 0xFF

            if is_on and i not in self._last_data[self.device_id]["ids"]:
                self._last_data[self.device_id]["ids"].append(i)
                self._last_data[self.device_id]["ids"].sort()
                _LOGGER.debug(
                    "New valid outlet discovered - Room: %s, Index: %s, Current valid indices: %s",
                    self.room_id, i, self._last_data[self.device_id]["ids"]
                )

            if i in self._last_data[self.device_id]["ids"]:
                device = Device(
                    device_type=self.device_name(),
                    room_id=self.room_id,
                    device_id=self.device_id,
                    state={POWER: is_on},
                    sub_id=str(i),
                )
                devices.append(device)

        return devices
    
    def make_scan(self) -> bytearray:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN, bytearray(8))
    
    def make_power_status(self, power: bool) -> bytearray:
        """Make a power status packet."""
        sub_id = int(self._device.sub_id)
        value = bytearray(self.value)
        value[sub_id] = 0xFF if power else 0x00
        return super().make_packet(Command.STATUS, value)
    

class ThermostatPacket(KocomPacket):
    """Handles packets for thermostat devices."""

    _class_last_data: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, packet: bytes) -> None:
        """Initialize the packet."""
        super().__init__(packet)
        if self.device_id not in self._class_last_data:
            self._class_last_data[self.device_id] = {
                "last_target_temp": 22,
            }
            self._class_last_data["is_hotwater"] = False
        self._last_data.update(self._class_last_data)

    def parse_data(self) -> list[Device]:
        """Parse thermostat-specific data."""
        devices: list[Device] = []

        is_on = self.value[0] >> 4 == 1
        is_hotwater = self.value[0] & 0x0F == 2
        is_away = self.value[1] & 0x0F == 1
        target_temp = self.value[2]
        hotwater_temp = self.value[3]
        current_temp = self.value[4]
        heatwater_temp = self.value[5]
        error_code = f"{self.value[6]:02}"
        is_error = error_code != "00"

        if is_on and self._last_data[self.device_id]["last_target_temp"] != target_temp:
            _LOGGER.debug(f"New target temperature: {target_temp}")
            self._last_data[self.device_id]["last_target_temp"] = target_temp

        devices.append(
            Device(
                device_type=self.device_name(),
                room_id=self.room_id,
                device_id=self.device_id,
                state={
                    POWER: is_on,
                    AWAY: is_away,
                    TARGET_TEMP: self._last_data[self.device_id]["last_target_temp"],
                    CURRENT_TEMP: current_temp,
                }
            )
        )
        devices.append(
            Device(
                device_type=self.device_name(),
                device_id=self.device_id,
                state={STATE: is_error, CODE: error_code},
                sub_id=ERROR,
            )
        )

        #if is_hotwater or self._last_data["is_hotwater"]:
        #    _LOGGER.debug(f"Hot water: {is_hotwater}")
        #    self._last_data["is_hotwater"] = True
        #    devices.append(
        #        Device(
        #            device_type=self.device_name(),
        #            device_id=self.device_id,
        #            state={POWER: is_hotwater},
        #            sub_id=HOTWATER,
        #        )
        #    )

        if hotwater_temp > 0:
            _LOGGER.debug(f"Hot water temperature: {hotwater_temp}.")
            devices.append(
                Device(
                    device_type=self.device_name(),
                    device_id=self.device_id,
                    state={STATE: hotwater_temp},
                    sub_id=f"{HOTWATER} {TEMPERATURE}",
                )
            )
        if heatwater_temp > 0:
            _LOGGER.debug(f"Heat water temperature: {heatwater_temp}.")
            devices.append(
                Device(
                    device_type=self.device_name(),
                    device_id=self.device_id,
                    state={STATE: heatwater_temp},
                    sub_id=f"{HEATWATER} {TEMPERATURE}",
                )
            )
            
        return devices
    
    def make_scan(self) -> bytearray:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN, bytearray(8))
    
    def make_power_status(self, power: bool) -> bytearray:
        """Make a power status packet."""
        value = bytearray(self.value)
        if power:
            value[0] = 0x11
            value[1] = 0x00
        else:
            value[0] = 0x00
            value[1] = 0x01
        return super().make_packet(Command.STATUS, value)
    
    def make_away_status(self, away_mode: bool) -> bytearray:
        """Make an away status packet."""
        value = bytearray(self.value)
        value[0] = 0x11
        value[1] = 0x01 if away_mode else 0x00
        return super().make_packet(Command.STATUS, value)
    
    def make_target_temp(self, target_temp: int) -> bytearray:
        """Make a target temperature packet."""
        value = bytearray(self.value)
        value[2] = target_temp
        return super().make_packet(Command.STATUS, value)


class ACPacket(KocomPacket):
    """Handles packets for AC devices."""

    class OperMode(IntEnum):
        """AC operation modes."""
        COOL = 0x00
        FAN_ONLY = 0x01
        DRY = 0x02
        AUTO = 0x03

    class FanMode(IntEnum):
        """AC fan modes."""
        UNKNOWN = 0x00
        LOW = 0x01
        MEDIUM = 0x02
        HIGH = 0x03

    def parse_data(self) -> list[Device]:
        """Parse AC-specific data."""
        is_on = self.value[0] == 0x10
        oper_mode = self.OperMode(self.value[1])
        fan_mode = self.FanMode(self.value[2])
        current_temp = self.value[4]
        target_temp = self.value[5]

        device = Device(
            device_type=self.device_name(capital=True),
            room_id=self.room_id,
            device_id=self.device_id,
            state={
                POWER: is_on,
                OPER_MODE: oper_mode,
                FAN_MODE: self.FanMode.LOW if fan_mode == self.FanMode.UNKNOWN else fan_mode,
                CURRENT_TEMP: current_temp,
                TARGET_TEMP: target_temp
            },
        )
        return [device]
    
    def make_scan(self) -> bytearray:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN, bytearray(8))
    
    def make_power_status(self, power: bool) -> bytearray:
        """Make a power status packet."""
        value = bytearray(self.value)
        value[0] = 0x10 if power else 0x00
        return super().make_packet(Command.STATUS, value)
    
    def make_oper_mode(self, oper_mode: OperMode) -> bytearray:
        """Make an operation mode packet."""
        value = bytearray(self.value)
        value[0] = 0x10
        value[1] = oper_mode.value
        return super().make_packet(Command.STATUS, value)
    
    def make_fan_mode(self, fan_mode: FanMode) -> bytearray:
        """Make a fan mode packet."""
        value = bytearray(self.value)
        value[2] = fan_mode.value
        return super().make_packet(Command.STATUS, value)
    
    def make_target_temp(self, target_temp: int) -> bytearray:
        """Make a target temperature packet."""
        value = bytearray(self.value)
        value[5] = target_temp
        return super().make_packet(Command.STATUS, value)
    

class FanPacket(KocomPacket):
    """Handles packets for fan devices."""

    class VentMode(IntEnum):
        """Fan vent modes."""
        UNKNOWN = 0x00
        VENTILATION = 0x01
        AUTO = 0x02
        BYPASS = 0x03
        NIGHT = 0x05
        AIR_PURIFIER = 0x08

    class FanSpeed(IntEnum):
        UNKNOWN = 0x00
        LOW = 0x40
        MEDIUM = 0x80
        HIGH = 0xC0

    _class_last_data: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, packet: bytes) -> None:
        """Initialize the packet."""
        super().__init__(packet)
        if self.device_id not in self._class_last_data:
            self._class_last_data[self.device_id] = {
                "is_co2_sensor": False,
            }
        self._last_data.update(self._class_last_data)
        
    def parse_data(self) -> list[Device]:
        """Parse fan-specific data."""
        devices: list[Device] = []

        is_on = self.value[0] >> 4 == 1
        vent_mode = self.VentMode(self.value[1])
        fan_speed = self.FanSpeed(self.value[2])
        co2_ppm = (self.value[4] * 100) + self.value[5]
        error_code = f"{self.value[7]:02}"
        is_error = error_code != "00"

        devices.append(
            Device(
                device_type=self.device_name(),
                room_id=self.room_id,
                device_id=self.device_id,
                state={
                    POWER: is_on and fan_speed != self.FanSpeed.UNKNOWN,
                    VENT_MODE: self.VentMode.VENTILATION if vent_mode == self.VentMode.UNKNOWN else vent_mode,
                    FAN_SPEED: self.FanSpeed.LOW if fan_speed == self.FanSpeed.UNKNOWN else fan_speed,
                }
            )
        )
        devices.append(
            Device(
                device_type=self.device_name(),
                device_id=self.device_id,
                state={STATE: is_error, CODE: error_code},
                sub_id=ERROR,
            )
        )
        
        if co2_ppm > 0 or self._class_last_data[self.device_id]["is_co2_sensor"]:
            _LOGGER.debug(f"CO2 ppm: {co2_ppm}")
            self._class_last_data[self.device_id]["is_co2_sensor"] = True
            devices.append(
                Device(
                    device_type=self.device_name(),
                    device_id=self.device_id,
                    state={STATE: co2_ppm},
                    sub_id=CO2,
                )
            )
    
        return devices
    
    def make_scan(self) -> bytearray:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN, bytearray(8))
    
    def make_power_status(self, power: bool) -> bytearray:
        """Make a power status packet."""
        value = bytearray(self.value)
        value[0] = 0x11 if power else 0x00
        return super().make_packet(Command.STATUS, value)
    
    def make_vent_mode(self, vent_mode: VentMode) -> bytearray:
        """Make a vent mode packet."""
        value = bytearray(self.value)
        value[0] = 0x11
        value[1] = vent_mode.value
        return super().make_packet(Command.STATUS, value)

    def make_fan_speed(self, fan_speed: FanSpeed) -> bytearray:
        """Make a fan speed packet."""
        value = bytearray(self.value)
        value[0] = 0x00 if fan_speed == self.FanSpeed.UNKNOWN else 0x11
        value[2] = fan_speed.value
        return super().make_packet(Command.STATUS, value)

    
class IAQPacket(KocomPacket):
    """Handles packets for IAQ devices."""

    def parse_data(self) -> list[Device]:
        """Parse IAQ-specific data."""
        devices: list[Device] = []

        sensor_mapping = {
            PM10: self.value[0],
            PM25: self.value[1],
            CO2: int.from_bytes(self.value[2:4], 'big'),
            VOC: int.from_bytes(self.value[4:6], 'big'),
            TEMPERATURE: self.value[6],
            HUMIDITY: self.value[7],
        }

        for sensor_id, value in sensor_mapping.items():
            if value > 0:
                _LOGGER.debug(f"{sensor_id}: {value}")
                device = Device(
                    device_type=self.device_name(capital=True),
                    device_id=self.device_id,
                    state={STATE: value},
                    sub_id=sensor_id,
                )
                devices.append(device)

        return devices
    
    def make_scan(self) -> bytearray:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN, bytearray(8))


class GasPacket(KocomPacket):
    """Handles packets for gas devices."""
    
    def parse_data(self) -> list[Device]:
        """Parse gas-specific data."""
        device = Device(
            device_type=self.device_name(),
            room_id=self.room_id,
            device_id=self.device_id,
            state={POWER: self.command == Command.ON},
        )
        return [device]
    
    def make_scan(self) -> bytearray:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN, bytearray(8))
    
    def make_power_status(self, power: bool) -> bytearray:
        """Make a power status packet."""
        if power:
            _LOGGER.debug(f"Gas device is on. Ignoring power status.")
            return
        return super().make_packet(Command.OFF, bytearray(self.value))
    

class MotionPacket(KocomPacket):
    """Handles packets for motion devices."""

    _class_last_data: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, packet: bytes) -> None:
        """Initialize the packet."""
        super().__init__(packet)
        if self.device_id not in self._class_last_data:
            self._class_last_data[self.device_id] = {
                "detect_time": None,
            }
        self._last_data.update(self._class_last_data)

    def parse_data(self) -> list[Device]:
        """Parse motion-specific data."""
        if is_detected := (self.command == Command.DETECT):
            _LOGGER.debug(f"Motion detected at {datetime.now()}")
            self._last_data[self.device_id]["detect_time"] = datetime.now()

        device = Device(
            device_type=self.device_name(),
            room_id=self.room_id,
            device_id=self.device_id,
            state={
                STATE: is_detected, TIME: self._last_data[self.device_id]["detect_time"]
            },
        )
        return [device]


class EVPacket(KocomPacket):
    """Handles packets for EV devices."""

    class Direction(IntEnum):
        """EV direction."""
        IDLE = 0x00
        DOWN = 0x01
        UP = 0x02
        ARRIVAL = 0x03

    _class_last_data: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, packet: bytes) -> None:
        """Initialize the packet."""
        super().__init__(packet)
        if self.device_id not in self._class_last_data:
            self._class_last_data[self.device_id] = {
                "avil_floor": False,
                "last_floor": None,
            }
        self._last_data.update(self._class_last_data)
        self._ev_invoke = False
        self._ev_direction = self.Direction(self.value[0])
        self._ev_floor = f"{self.value[1]:02}"

    def parse_data(self) -> list[Device]:
        """Parse EV-specific data."""
        devices: list[Device] = []

        devices.append(
            Device(
                device_type=self.device_name(capital=True),
                room_id=self.room_id,
                device_id=self.device_id,
                state={POWER: self._ev_invoke},
            )
        )
        devices.append(
            Device(
                device_type=self.device_name(capital=True),
                room_id=self.room_id,
                device_id=self.device_id,
                state={STATE: self._ev_direction.name},
                sub_id=DIRECTION,
            )
        )

        if int(self._ev_floor) >> 4 == 0x08:   # 지하 층
            self._ev_floor = f"B{str(int(self._ev_floor) & 0x0F)}"

        if self._ev_floor != "00" or self._last_data[self.device_id]["avil_floor"]:
            self._last_data[self.device_id]["avil_floor"] = True
            self._last_data[self.device_id]["last_floor"] = self._ev_floor
            _LOGGER.debug(f"EV floor: {self._ev_floor}")

            devices.append(
                Device(
                    device_type=self.device_name(capital=True),
                    room_id=self.room_id,
                    device_id=self.device_id,
                    state={STATE: self._last_data[self.device_id]["last_floor"]},
                    sub_id=FLOOR,
                )
            )
        
        if self._ev_direction == self.Direction.ARRIVAL:
            self._ev_invoke = False
            self._ev_direction = self.Direction.IDLE
        
        return devices
    
    def make_power_status(self, power: bool) -> bytearray:
        """Make a power status packet."""
        if not power:
            _LOGGER.debug(f"EV device is off. Ignoring power status.")
            return
        self._ev_invoke = True
        return super().make_packet(Command.ON, bytearray(self.value))


class PacketParser:
    """Parses raw Kocom packets into specific device classes."""

    @staticmethod
    def parse(packet_data: bytes) -> KocomPacket:
        """Parse a raw packet into a specific packet class."""
        if packet_data[7] == DeviceType.WALLPAD.value:
            device_type = packet_data[5]
        else:
            device_type = packet_data[7]
        return PacketParser._get_packet_instance(device_type, packet_data)

    @staticmethod
    def parse_state(packet: bytes, last_data: dict[str, Any] = None) -> list[KocomPacket]:
        """Parse device states from a packet."""
        base_packet = PacketParser.parse(packet)
        
        if (
            base_packet.packet_type == PacketType.RECV and
            base_packet.command == Command.SCAN
        ):
            return [base_packet]

        # Update base packet's last_data if provided
        if last_data:
            base_packet._last_data.update(last_data)

        # Generate packets for each device
        parsed_packets: list[KocomPacket] = []
        for device_data in base_packet.parse_data():
            device_packet = deepcopy(base_packet)
            device_packet._device = device_data
            parsed_packets.append(device_packet)
        
        return parsed_packets

    @staticmethod
    def _get_packet_instance(device_type: int, packet_data: bytes) -> KocomPacket:
        """Retrieve the appropriate packet class based on device type."""
        device_class_map = {
            DeviceType.LIGHT.value: LightPacket,
            DeviceType.OUTLET.value: OutletPacket,
            DeviceType.THERMOSTAT.value: ThermostatPacket,
            DeviceType.AC.value: ACPacket,
            DeviceType.FAN.value: FanPacket,
            DeviceType.IAQ.value: IAQPacket,
            DeviceType.GAS.value: GasPacket,
            DeviceType.MOTION.value: MotionPacket,
            DeviceType.EV.value: EVPacket,
            DeviceType.WALLPAD.value: KocomPacket,
        }

        packet_class = device_class_map.get(device_type)
        if packet_class is None:
            _LOGGER.error(f"Unknown device type: {hex(device_type)}, data: {packet_data.hex()}")
            return KocomPacket(packet_data)
        
        return packet_class(packet_data)


class DoorPhonePacket:
    """Represents a door phone packet."""

    _last_data: dict[str, Any] = {}

    def __init__(self, packet: bytes) -> None:
        """Initialize the DoorPhonePacket."""
        self.packet = packet
        self.dest = packet[4]
        self.src = packet[5]
        self.src2 = packet[11]
        self.event = packet[15]
        self.event2 = packet[16]

        self.device_type = "doorphone"
        self.room_id = self.entrance_type.name.lower()
        self.device_id = f"{self.device_type}_{self.room_id}"
        self._device: Device = None

        if self.device_id not in self._last_data:
            self._last_data[self.device_id] = {}
    
        self._last_data[self.device_id].update({
            "ringing_time": None,
        })
        self._last_data["phone_id"] = None
        self._phone_opening = False
        self._phone_exiting = False

    def __repr__(self) -> str:
        """Return a string representation of the DoorPhonePacket."""
        return f"DoorPhonePacket(packet={self.packet.hex()}, dest={self.dest}, src={self.src}, src2={self.src2}, event={self.event}, event2={self.event2})"
    
    @property
    def entrance_type(self) -> DoorPhoneEntrance:
        """Get the entrance type."""
        if self.dest == 0x02 and self.src == 0x02:
            return DoorPhoneEntrance.PRIVATE
        else:
            return DoorPhoneEntrance.PUBLIC
        
    def parse_data(self) -> list[Device]:
        """Parse door phone-specific data."""
        devices: list[Device] = []
        if is_ringing := (self.event == 0x01 and self.event2 == 0x01):
            _LOGGER.debug(f"Door phone - {self.room_id} ringing at {datetime.now()}")
            self._last_data[self.device_id]["ringing_time"] = datetime.now()
        
        if self._last_data["phone_id"] is None and self.src2 not in {0xFF, 0x31}:
            self._last_data["phone_id"] = self.src2
            _LOGGER.debug(f"Door phone - {self.room_id} phone id: {self._last_data['phone_id']:#x}")
        
        if self.event == 0x24 and self.event == 0x00:
            _LOGGER.debug(f"Door phone - {self.room_id} opening at {datetime.now()}")
            self._phone_opening = False
        if self.event == 0x04 and self.event2 == 0x00:
            _LOGGER.debug(f"Door phone - {self.room_id} exiting at {datetime.now()}")
            self._phone_exiting = False

        devices.append(
            Device(
                device_type=self.device_type,
                device_id=self.device_id,
                room_id=self.room_id,
                state={
                    STATE: is_ringing,
                    TIME: self._last_data[self.device_id]["ringing_time"],
                },
                sub_id=RING,
            )
        )
        devices.append(
            Device(
                device_type=self.device_type,
                device_id=self.device_id,
                room_id=self.room_id,
                state={POWER: self._phone_opening},
            )
        )
        devices.append(
            Device(
                device_type=self.device_type,
                device_id=self.device_id,
                room_id=self.room_id,
                state={POWER: self._phone_exiting},
                sub_id=SHUTDOWN,
            )
        )

        return devices
    
    def make_door_phone_packets(self, command_packet: list[tuple[bytearray, float | None]]) -> None:
        """Make door phone packets."""
        make_packets = []
        base_packet = bytearray([
            0x79, 0xBC, self.src, self.dest,
            0x00, self.src2, 0xFF, 0xFF, 0xFF,
            self._last_data["phone_id"] or 0x2A,
            0xFF, 0xFF, 0xFF
        ])
        for cmd, delay in command_packet:
            make_packet = base_packet.copy()
            make_packet.extend(cmd)
            make_packets.append((make_packet, delay))

        _LOGGER.debug(f"Door phone make packets: {make_packets}")
        return make_packets
    
    def make_power_status(self, power: bool, control: str | None) -> list[tuple[bytearray, float | None]]:
        """Make a packet to set the power status of the door phone."""
        if not power:
            _LOGGER.debug(f"Door phone device is off - {control}. Ignoring power status.")
            return
        
        open_packet = [
            (bytearray([0x03, 0x00]), 1.0),
            (bytearray([0x24, 0x00]), 0.1),
            (bytearray([0x04, 0x00]), 1.0),
        ]
        shutdown_packet = [
            (bytearray([0x03, 0x00]), 1.0),
            (bytearray([0x04, 0x00]), 1.0),
        ]

        if control == SHUTDOWN:
            self._phone_exiting = True
            return self.make_door_phone_packets(shutdown_packet)
        else:
            self._phone_opening = True
            return self.make_door_phone_packets(open_packet)


class DoorPhoneParser:
    """Parser for door phone packets."""

    @staticmethod
    def parse_state(packet: bytes, last_data: dict[str, Any] = None) -> list[DoorPhonePacket]:
        """Parse door phone packets."""
        base_packet = DoorPhonePacket(packet)
        
        #if (
        #    base_packet.entrance_type is None or
        #    base_packet.event_type is None
        #):
        #    _LOGGER.debug(f"Unknown door phone packet: {packet.hex()}")
        #    return [base_packet]

        # Update base packet's last_data if provided
        if last_data:
            base_packet._last_data.update(last_data)

        # Generate packets for each device
        parsed_packets: list[DoorPhonePacket] = []
        for device_data in base_packet.parse_data():
            device_packet = deepcopy(base_packet)
            device_packet._device = device_data
            parsed_packets.append(device_packet)
        
        return parsed_packets
    