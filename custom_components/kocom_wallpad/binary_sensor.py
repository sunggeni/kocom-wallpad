"""Binary Sensor Platform for Kocom Wallpad."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .pywallpad.const import STATE, ERROR_CODE
from .pywallpad.packet import KocomPacket, ThermostatPacket

from .gateway import KocomGateway
from .entity import KocomEntity
from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kocom binary sensor platform."""
    gateway: KocomGateway = hass.data[DOMAIN][entry.entry_id]
    
    @callback
    def async_add_binary_sensor(packet: KocomPacket) -> None:
        """Add new binary sensor entity."""
        if isinstance(packet, ThermostatPacket):
            async_add_entities([KocomBinarySensorEntity(gateway, packet)])
        else:
            LOGGER.warning(f"Unsupported packet type: {packet}")
    
    for entity in gateway.get_entities(Platform.BINARY_SENSOR):
        async_add_binary_sensor(entity)
        
    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_binary_sensor_add", async_add_binary_sensor)
    )


class KocomBinarySensorEntity(KocomEntity, BinarySensorEntity):
    """Representation of a Kocom binary sensor."""
    
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        gateway: KocomGateway,
        packet: KocomPacket,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(gateway, packet)
        self._attr_extra_state_attributes = {
            ERROR_CODE: self.device.state[ERROR_CODE]
        }

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.device.state[STATE]
    