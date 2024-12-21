"""Packet class for py wallpad."""

from __future__ import annotations

from typing import Any
from copy import deepcopy
from dataclasses import dataclass, field
import time

from .const import (
    _LOGGER,
    POWER,
    BRIGHTNESS,
    LEVEL,
    AWAY_MODE,
    TARGET_TEMP,
    CURRENT_TEMP,
    STATE,
    ERROR_CODE,
    HOTWATER_TEMP,
    HEATWATER_TEMP,
    OP_MODE,
    FAN_MODE,
    VENT_MODE,
    FAN_SPEED,
    PM10,
    PM25,
    CO2,
    VOC,
    TEMPERATURE,
    HUMIDITY,
    TIME,
)
from .crc import verify_checksum, calculate_checksum
from .enums import (
    DeviceType,
    PacketType,
    Command,
    OpMode,    # AC 
    FanMode,   # AC
    VentMode,  # Fan
    FanSpeed,  # Fan
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

    def __init__(self, packet: list[str]) -> None:
        """Initialize the packet."""
        self.packet = packet
        self.packet_type = PacketType(packet[3][0])
        self.sequence = packet[3][1]
        self.dest = packet[5:7]
        self.src = packet[7:9]
        self.command = Command(packet[9])
        self.value = packet[10:18]
        self.checksum = packet[18]
        self._device: Device = None

    def __repr__(self) -> str:
        """Return a string representation of the packet."""
        return f"KocomPacket(packet={self.packet}, packet_type={self.packet_type}, sequence={self.sequence}, dest={self.dest}, src={self.src}, command={self.command}, value={self.value}, checksum={self.checksum}, device={self._device})"
    
    @property
    def device_type(self) -> DeviceType:
        """Return the device type."""
        return DeviceType(self.src[0])
    
    @property
    def room_id(self) -> str:
        """Return the room ID."""
        return str(self.src[1])
    
    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device_type.name.lower()
    
    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return f"{self.name}_{self.room_id}"
    
    def parse_data(self) -> list[Device]:
        """Parse data from the packet."""
        _LOGGER.warning("Parsing not implemented for %s", self.name)
        return []
    
    def make_packet(self, command: Command, values: dict[int, int] = None) -> bytearray:
        """Generate a packet."""
        packet = bytearray([0xaa, 0x55, 0x30, 0xbc, 0x00])
    
        packet.extend(int(x, 16) for x in self.src)
        packet.extend(int(x, 16) for x in self.dest)
        packet.append(int(command.value, 16))
        packet.extend([0x00] * 8)
        
        if values:
            for index, val in values.items():
                packet[10 + index] = val

        checksum = calculate_checksum(packet)
        if checksum is None:
            _LOGGER.error(f"Checksum calculation failed: {packet.hex()}")
            return bytearray()

        packet.append(checksum)
        packet.extend([0x0d, 0x0d])

        if not verify_checksum(packet):
            _LOGGER.error(f"Packet checksum verification failed: {packet.hex()}")
            return bytearray()
        
        return packet


class LightPacket(KocomPacket):
    """Handles packets for light devices."""
    valid_light_indices: dict[int, dict[int, list[int]]] = {} 
    # {room_id: {sub_index: [brightness_levels]}}

    def parse_data(self) -> list[Device]:
        """Parse light-specific data."""
        devices: list[Device] = []

        if self.room_id not in self.valid_light_indices:
            self.valid_light_indices[self.room_id] = {}
        
        for i, value in enumerate(self.value[:8]):
            power_state = value == "ff"
            brightness = int(value, 16) if value != "ff" else 0

            if power_state and i not in self.valid_light_indices[self.room_id]:
                self.valid_light_indices[self.room_id][i] = []
            
            if (brightness > 0 and 
                i in self.valid_light_indices[self.room_id] and
                brightness not in self.valid_light_indices[self.room_id][i]
            ):
                self.valid_light_indices[self.room_id][i].append(brightness)
                self.valid_light_indices[self.room_id][i].sort()
                _LOGGER.debug(
                    "New brightness level discovered - Room: %s, Index: %s, Level: %s, Current levels: %s",
                    self.room_id, i, brightness, self.valid_light_indices[self.room_id][i]
                )
            
            if i in self.valid_light_indices[self.room_id]:
                state = {POWER: power_state}
                has_brightness = bool(self.valid_light_indices[self.room_id][i])

                if has_brightness:
                    state[POWER] = int(value, 16) > 0
                    state[BRIGHTNESS] = brightness
                    state[LEVEL] = self.valid_light_indices[self.room_id][i]
                
                device = Device(
                    device_type=self.name,
                    room_id=self.room_id,
                    device_id=self.device_id,
                    state=state,
                    sub_id=str(i),
                )
                devices.append(device)
                
        return devices
    
    def make_scan(self) -> None:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN)
    
    def make_status(self, **kwargs) -> None:
        """Make a status packet."""
        values = {}
        control_mode, control = next(iter(kwargs.items()))
        sub_id = self._device.sub_id
        if control_mode == POWER and sub_id:
            values[int(sub_id)] = 0xff if control else 0x00
        elif control_mode == BRIGHTNESS and sub_id:
            values[int(sub_id)] = control
        else:
            raise ValueError(f"Invalid control mode: {control_mode}")

        return super().make_packet(Command.STATUS, values)


class OutletPacket(KocomPacket):
    """Handles packets for outlet devices."""
    valid_outlet_indices: dict[int, list[int]] = {}
    # {room_id: [sub_index, ..]}, {room_id: [sub_index, ..]}, ...

    def parse_data(self) -> list[Device]:
        """Parse outlet-specific data."""
        devices: list[Device] = []

        if self.room_id not in self.valid_outlet_indices:
            self.valid_outlet_indices[self.room_id] = []
        
        for i, value in enumerate(self.value[:8]):
            power_state = value == "ff"

            if power_state and i not in self.valid_outlet_indices[self.room_id]:
                self.valid_outlet_indices[self.room_id].append(i)
                _LOGGER.debug(
                    "New valid outlet discovered - Room: %s, Index: %s, Current valid indices: %s",
                    self.room_id, i, self.valid_outlet_indices[self.room_id]
                )

            if i in self.valid_outlet_indices[self.room_id]:
                device = Device(
                    device_type=self.name,
                    room_id=self.room_id,
                    device_id=self.device_id,
                    state={POWER: power_state},
                    sub_id=str(i),
                )
                devices.append(device)

        return devices

    def make_scan(self) -> None:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN)
    
    def make_status(self, **kwargs) -> None:
        """Make a status packet."""
        values = {}
        control_mode, control = next(iter(kwargs.items()))
        if control_mode == POWER and (sub_id := self._device.sub_id):
            values[int(sub_id)] = 0xff if control else 0x00
        else:
            raise ValueError(f"Invalid control mode: {control_mode}")

        return super().make_packet(Command.STATUS, values)
    

class ThermostatPacket(KocomPacket):
    """Handles packets for thermostat devices."""

    def parse_data(self) -> list[Device]:
        """Parse thermostat-specific data."""
        devices: list[Device] = []

        power_state = self.value[0][0] == "1"
        hotwater_state = self.value[0][1] == "2"
        away_mode = self.value[1][1] == "1"
        target_temp = int(self.value[2], 16)
        current_temp = int(self.value[4], 16)
        hotwater_temp = int(self.value[3], 16)
        heatwater_temp = int(self.value[5], 16)
        error_code = int(self.value[6], 16)
        boiler_error = int(self.value[7], 16)
        
        devices.append(
            Device(
                device_type=self.name,
                room_id=self.room_id,
                device_id=self.device_id,
                state={
                    POWER: power_state,
                    AWAY_MODE: away_mode,
                    TARGET_TEMP: target_temp,
                    CURRENT_TEMP: current_temp,
                },
            )
        )

        if self.room_id == "00":
            devices.append(
                Device(
                    device_type=self.name,
                    device_id=self.device_id,
                    state={STATE: error_code != 0, ERROR_CODE: error_code},
                    sub_id="error",
                )
            )
            devices.append(
                Device(
                    device_type=self.name,
                    device_id=self.device_id,
                    state={STATE: boiler_error != 0, ERROR_CODE: boiler_error},
                    sub_id="boiler error",
                )
            )

        if hotwater_state and self.room_id == "00":
            _LOGGER.debug(f"Supports hot water in thermostat.")

            if hotwater_temp > 0:
                _LOGGER.debug(f"Supports hot water temperature in thermostat.")
                devices.append(
                    Device(
                        device_type=self.name,
                        room_id=None,
                        device_id=self.device_id,
                        state={HOTWATER_TEMP: hotwater_temp},
                        sub_id="hotwater temperature",
                    )
                )
            if heatwater_temp > 0:
                _LOGGER.debug(f"Supports heat water temperature in thermostat.")
                devices.append(
                    Device(
                        device_type=self.name,
                        room_id=None,
                        device_id=self.device_id,
                        state={HEATWATER_TEMP: heatwater_temp},
                        sub_id="heatwater temperature",
                    )
                )
            
        return devices
    
    def make_scan(self) -> None:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN)

    def make_status(self, **kwargs) -> None:
        """Make a status packet."""
        values = {}
        control_mode, control = next(iter(kwargs.items()))
        if control_mode == POWER:
            values[0] = 0x11 if control else 0x01
            values[1] = 0x00
        elif control_mode == AWAY_MODE:
            values[0] = 0x11
            values[1] = 0x01 if control else 0x00
        elif control_mode == TARGET_TEMP:
            values[2] = int(control)
        else:
            raise ValueError(f"Unsupported control mode: {control_mode}")
        
        return super().make_packet(Command.STATUS, values)


class AcPacket(KocomPacket):
    """Handles packets for AC devices."""

    def parse_data(self) -> list[Device]:
        """Parse AC-specific data."""
        power_state = self.value[0] == "10"
        op_mode = OpMode(self.value[1])
        fan_mode = FanMode(self.value[2])
        current_temp = int(self.value[4], 16)
        target_temp = int(self.value[5], 16)

        device = Device(
            device_type=self.name,
            room_id=self.room_id,
            device_id=self.device_id,
            state={
                POWER: power_state,
                OP_MODE: op_mode,
                FAN_MODE: fan_mode,
                CURRENT_TEMP: current_temp,
                TARGET_TEMP: target_temp
            },
        )
        return [device]
    
    def make_scan(self) -> None:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN)
    
    def make_status(self, **kwargs) -> None:
        """Make a status packet."""
        values = {}
        control_mode, control = next(iter(kwargs.items()))
        if control_mode == POWER:
            values[0] = 0x10 if control else 0x00
        elif control_mode == OP_MODE:
            values[1] = int(control.value, 16)
        elif control_mode == FAN_MODE:
            values[2] = int(control.value, 16)
        elif control_mode == TARGET_TEMP:
            values[5] = int(control)
        else:
            raise ValueError(f"Unsupported control mode: {control_mode}")
        
        return super().make_packet(Command.STATUS, values)


class FanPacket(KocomPacket):
    """Handles packets for fan devices."""
    co2_supported = False
    
    def parse_data(self) -> list[Device]:
        """Parse fan-specific data."""
        devices: list[Device] = []

        power_state = self.value[0][0] == "1"
        co2_sensor = self.value[0][1] == "1"
        vent_mode = VentMode(self.value[1])
        fan_speed = FanSpeed(self.value[2])
        co2_state = int(''.join(self.value[4:6]), 16)
        error_code = int(self.value[6], 16)
        
        devices.append(
            Device(
                device_type=self.name,
                room_id=self.room_id,
                device_id=self.device_id,
                state={POWER: power_state, VENT_MODE: vent_mode, FAN_SPEED: fan_speed}
            )
        )
        devices.append(
            Device(
                device_type=self.name,
                device_id=self.device_id,
                state={STATE: error_code != 0, ERROR_CODE: error_code},
                sub_id="error",
            )
        )
        
        if co2_sensor or self.co2_supported:
            _LOGGER.debug(f"Supports CO2 sensor in fan.")
            self.co2_supported = True
            devices.append(
                Device(
                    device_type=self.name,
                    room_id=self.room_id,
                    device_id=self.device_id,
                    state={STATE: co2_state},
                    sub_id=CO2,
                )
            )
    
        return devices

    def make_scan(self) -> None:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN)

    def make_status(self, **kwargs) -> None:
        """Make a status packet."""
        values = {}
        control_mode, control = next(iter(kwargs.items()))
        if control_mode == POWER:
            values[0] = 0x11 if control else 0x00
        elif control_mode == VENT_MODE:
            values[0] = 0x11
            values[1] = int(control.value, 16)
        elif control_mode == FAN_SPEED:
            values[0] = 0x00 if control == FanSpeed.OFF else 0x11
            values[2] = int(control.value, 16)
        else:
            raise ValueError(f"Unsupported control mode: {control_mode}")
        
        return super().make_packet(Command.STATUS, values)
    
    
class IAQPacket(KocomPacket):
    """Handles packets for IAQ devices."""

    def parse_data(self) -> list[Device]:
        """Parse IAQ-specific data."""
        devices: list[Device] = []

        sensor_mapping = {
            PM10: int(self.value[0], 16),
            PM25: int(self.value[1], 16),
            CO2: int(''.join(self.value[2:4]), 16),
            VOC: int(''.join(self.value[4:6]), 16),
            TEMPERATURE: int(self.value[6], 16),
            HUMIDITY: int(self.value[7], 16),
        }

        for sensor_id, state in sensor_mapping.items():
            if state > 0:
                _LOGGER.debug(f"Supports {sensor_id} in IAQ.")
                device = Device(
                    device_type=self.name,
                    device_id=self.device_id,
                    state={STATE: state},
                    sub_id=sensor_id,
                )
                devices.append(device)

        return devices


class GasPacket(KocomPacket):
    """Handles packets for gas devices."""
    
    def parse_data(self) -> list[Device]:
        """Parse gas-specific data."""
        power_state = self.command == Command.ON
        device = Device(
            device_type=self.name,
            room_id=self.room_id,
            device_id=self.device_id,
            state={POWER: power_state},
        )
        return [device]
    
    def make_scan(self) -> None:
        """Make a scan packet."""
        return super().make_packet(Command.SCAN)
    
    def make_status(self, power: bool) -> None:
        """Make a status packet."""
        if not power:
            return super().make_packet(Command.OFF)
        else:
            _LOGGER.debug("Supports gas valve lock only.")
    

class MotionPacket(KocomPacket):
    """Handles packets for motion devices."""

    def parse_data(self) -> list[Device]:
        """Parse motion-specific data."""
        detect_state = self.command == Command.DETECT
        detect_time = time.time()
        device = Device(
            device_type=self.name,
            room_id=self.room_id,
            device_id=self.device_id,
            state={STATE: detect_state, TIME: detect_time},
        )
        return [device]


class PacketParser:
    """Parses raw Kocom packets into specific classes."""

    @staticmethod
    def parse(packet: str) -> KocomPacket:
        """Parse a raw packet."""
        packet_list = [packet[i:i + 2] for i in range(0, len(packet), 2)]
        device_type = packet_list[7]
        return PacketParser.get_packet_class(device_type, packet_list)
    
    @staticmethod
    def parse_state(packet: str) -> list[KocomPacket]:
        """Parse the state from a packet."""
        parsed_packet = PacketParser.parse(packet)
        if parsed_packet.device_type == DeviceType.WALLPAD:
            return []
        if parsed_packet.packet_type == PacketType.RECV and parsed_packet.command == Command.SCAN:
            return []
        
        packets: list[KocomPacket] = []
        for device in parsed_packet.parse_data():
            new_packet = deepcopy(parsed_packet)
            new_packet._device = device
            packets.append(new_packet)
        
        return packets
    
    @staticmethod
    def get_packet_class(device_type: str, packet_list: list[str]) -> KocomPacket:
        """Return the appropriate packet class based on device type."""
        packet_class_map = {
            DeviceType.LIGHT.value: LightPacket,
            DeviceType.OUTLET.value: OutletPacket,
            DeviceType.THERMOSTAT.value: ThermostatPacket,
            DeviceType.AC.value: AcPacket,
            DeviceType.FAN.value: FanPacket,
            DeviceType.IAQ.value: IAQPacket,
            DeviceType.GAS.value: GasPacket,
            DeviceType.MOTION.value: MotionPacket,
            DeviceType.WALLPAD.value: KocomPacket,
        }
        packet_class = packet_class_map.get(device_type)
        if packet_class is None:
            _LOGGER.error("Unknown device type: %s, %s", device_type, packet_list)
            return KocomPacket(packet_list)
        
        return packet_class(packet_list)
    