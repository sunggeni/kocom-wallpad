"""Entity classes for Kocom Wallpad."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity, RestoredExtraData
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .pywallpad.packet import Device, KocomPacket

from .gateway import KocomGateway
from .util import create_dev_id
from .const import (
    DOMAIN,
    BRAND_NAME,
    MANUFACTURER,
    MODEL,
    SW_VERSION,
    DEVICE_TYPE,
    ROOM_ID,
    SUB_ID,
    PACKET,
)


class KocomEntity(RestoreEntity):
    """Base class for Kocom Wallpad entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    
    def __init__(
        self,
        gateway: KocomGateway,
        packet: KocomPacket,
    ) -> None:
        """Initialize the Kocom Wallpad entity."""
        self.gateway = gateway
        self.packet = packet
        self.device = packet._device
        self.device_update_signal = f"{DOMAIN}_{self.gateway.host}_{self.device_id}"
        
        self._attr_unique_id = f"{BRAND_NAME}_{self.device_id}-{self.gateway.host}"
        self._attr_name = f"{BRAND_NAME} {self.name}"
        self._attr_extra_state_attributes = {
            DEVICE_TYPE: self.device.device_type,
            ROOM_ID: self.device.room_id,
            SUB_ID: self.device.sub_id,
        }
        
    @property
    def device_id(self) -> str:
        """Return the device id."""
        return create_dev_id(
            self.device.device_type, self.device.room_id, self.device.sub_id
        )
    
    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.device_id.replace("_", " ").title()
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.gateway.host}_{self.device.device_type}")},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"{BRAND_NAME.title()} {self.device.device_type}",
            sw_version=SW_VERSION,
            via_device=(DOMAIN, self.gateway.host),
        )
        
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.gateway.connection.is_connected()
    
    @callback
    def async_handle_device_update(self, device: Device) -> None:
        """Handle device update."""
        if self.device.state != device.state:
            self.device.state = device.state
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.device_update_signal, self.async_handle_device_update)
        )
    
    @property
    def extra_restore_state_data(self) -> RestoredExtraData:
        """Return extra state data to be restored."""
        return RestoredExtraData({PACKET: ''.join(self.packet.packet)})
    
    async def send(self, packet: bytes) -> None:
        """Send a packet to the gateway."""
        await self.gateway.client.send(packet)
