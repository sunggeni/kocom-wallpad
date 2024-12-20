"""Climate platform for Kocom Wallpad."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    PRESET_AWAY,
    PRESET_NONE,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)

from homeassistant.const import Platform, UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .pywallpad.const import (
    POWER,
    AWAY_MODE,
    OP_MODE,
    FAN_MODE,
    CURRENT_TEMP,
    TARGET_TEMP,
)
from .pywallpad.enums import OpMode, FanMode
from .pywallpad.packet import KocomPacket, ThermostatPacket, AcPacket

from .gateway import KocomGateway
from .entity import KocomEntity
from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kocom climate platform."""
    gateway: KocomGateway = hass.data[DOMAIN][entry.entry_id]
    
    @callback
    def async_add_climate(packet: KocomPacket) -> None:
        """Add new climate entity."""
        if isinstance(packet, ThermostatPacket):
            async_add_entities([KocomThermostatEntity(gateway, packet)])
        elif isinstance(packet, AcPacket):
            async_add_entities([KocomAcEntity(gateway, packet)])
        else:
            LOGGER.warning(f"Unsupported packet type: {packet}")
    
    for entity in gateway.get_entities(Platform.CLIMATE):
        async_add_climate(entity)
        
    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_climate_add", async_add_climate)
    )


class KocomThermostatEntity(KocomEntity, ClimateEntity):
    """Representation of a Kocom climate."""

    _enable_turn_on_off_backwards_compatibility = False
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = [PRESET_AWAY, PRESET_NONE]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | 
        ClimateEntityFeature.TURN_OFF | 
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = 40
    _attr_min_temp = 5
    _attr_target_temperature_step = 1
    
    def __init__(
        self,
        gateway: KocomGateway,
        packet: KocomPacket,
    ) -> None:
        """Initialize the climate."""
        super().__init__(gateway, packet)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self.device.state[POWER]:
            return HVACMode.HEAT
        else:
            return HVACMode.OFF
        
    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        if self.device.state[AWAY_MODE]:
            return PRESET_AWAY
        else:
            return PRESET_NONE

    @property
    def current_temperature(self) -> int:
        """Return the current temperature."""
        return self.device.state[CURRENT_TEMP]

    @property
    def target_temperature(self) -> int:
        """Return the temperature we try to reach."""
        return self.device.state[TARGET_TEMP]
    
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            power = False
        elif hvac_mode == HVACMode.HEAT:
            power = True
        else:
            raise ValueError(f"Unknown HVAC mode: {hvac_mode}")
        
        packet = self.packet.make_status(power=power)
        await self.send(packet)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode == PRESET_AWAY:
            away_mode = True
        elif preset_mode == PRESET_NONE:
            away_mode = False
        else:
            raise ValueError(f"Unknown preset mode: {preset_mode}")
        
        packet = self.packet.make_status(away_mode=away_mode)
        await self.send(packet)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            LOGGER.warning("Missing temperature")
            return
        
        packet = self.packet.make_status(target_temp=target_temp)
        await self.send(packet)


class KocomAcEntity(KocomEntity, ClimateEntity):
    """Representation of a Kocom climate."""

    _enable_turn_on_off_backwards_compatibility = False
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.AUTO
    ]
    _attr_fan_modes = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | 
        ClimateEntityFeature.TURN_OFF | 
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.FAN_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = 30
    _attr_min_temp = 18
    _attr_target_temperature_step = 1
    
    def __init__(
        self,
        gateway: KocomGateway,
        packet: KocomPacket,
    ) -> None:
        """Initialize the climate."""
        super().__init__(gateway, packet)
        
    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self.device.state[POWER] and (op_mode := self.device.state[OP_MODE]):
            if op_mode == OpMode.COOL:
                return HVACMode.COOL
            elif op_mode == OpMode.FAN_ONLY:
                return HVACMode.FAN_ONLY
            elif op_mode == OpMode.DRY:
                return HVACMode.DRY
            elif op_mode == OpMode.AUTO:
                return HVACMode.AUTO
        else:
            return HVACMode.OFF
    
    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        fan_mode = self.device.state[FAN_MODE]
        if fan_mode == FanMode.LOW:
            return FAN_LOW
        elif fan_mode == FanMode.MEDIUM:
            return FAN_MEDIUM
        elif fan_mode == FanMode.HIGH:
            return FAN_HIGH
        
    @property
    def current_temperature(self) -> int:
        """Return the current temperature."""
        return self.device.state[CURRENT_TEMP]

    @property
    def target_temperature(self) -> int:
        """Return the temperature we try to reach."""
        return self.device.state[TARGET_TEMP]
    
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            op_mode = OpMode.OFF
        elif hvac_mode == HVACMode.COOL:
            op_mode = OpMode.COOL
        elif hvac_mode == HVACMode.FAN_ONLY:
            op_mode = OpMode.FAN_ONLY
        elif hvac_mode == HVACMode.DRY:
            op_mode = OpMode.DRY
        elif hvac_mode == HVACMode.AUTO:
           op_mode = OpMode.AUTO
        else:
            raise ValueError(f"Unknown HVAC mode: {hvac_mode}")
               
        packet = self.packet.make_status(op_mode=op_mode)
        await self.send(packet)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode == FAN_LOW:
            fan_speed = FanMode.LOW
        elif fan_mode == FAN_MEDIUM:
            fan_speed = FanMode.MEDIUM
        elif fan_mode == FAN_HIGH:
            fan_speed = FanMode.HIGH
        else:
            raise ValueError(f"Unknown fan mode: {fan_mode}")
        
        packet = self.packet.make_status(fan_mode=fan_speed)
        await self.send(packet)
        
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            LOGGER.warning("Missing temperature")
            return
        
        packet = self.packet.make_status(target_temp=target_temp)
        await self.send(packet)
