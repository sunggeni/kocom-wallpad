from __future__ import annotations

from typing import Optional

import asyncio
import re
import serial_asyncio

from .const import LOGGER


class RS485Connection:
    """Connection class for RS485 communication with IP or serial support."""

    def __init__(self, host: str, port: Optional[int] = None):
        """Initialize the connection."""
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.is_connected = False
        self.reconnect_interval = 5
        self._running = True

    def is_ip_address(self) -> bool:
        """Check if the host is an IP address."""
        ip_pattern = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
        return bool(ip_pattern.match(self.host))

    async def connect(self) -> bool:
        """Connect to the device using IP or serial."""
        try:
            if self.is_ip_address():
                if not self.port:
                    raise ValueError("Port must be provided for IP connections.")
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port
                )
                LOGGER.info(f"Connected to {self.host}:{self.port}")
            else:
                self.reader, self.writer = await serial_asyncio.open_serial_connection(
                    url=self.host, baudrate=9600
                )
                LOGGER.info(f"Connected to serial port {self.host}")
            
            self.is_connected = True
            return True
        except Exception as e:
            LOGGER.error(f"Connection failed: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from the device."""
        self._running = False
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                LOGGER.error(f"Disconnect error: {e}")
        self.is_connected = False

    async def reconnect_manager(self):
        """Reconnect to the device."""
        while self._running:
            if not self.is_connected:
                success = await self.connect()
                if not success:
                    await asyncio.sleep(self.reconnect_interval)
            await asyncio.sleep(1)

    async def send(self, packet: bytearray) -> bool:
        """Send packet to the device."""
        if not self.is_connected or not self.writer:
            return False
        try:
            self.writer.write(packet)
            await self.writer.drain()
            return True
        except ConnectionResetError:
            LOGGER.error("Connection reset by peer")
            self.is_connected = False
            return False
        except Exception as e:
            LOGGER.error(f"Send error: {e}")
            self.is_connected = False
            return False

    async def receive(self) -> Optional[bytes]:
        """Receive data from the device."""
        if not self.is_connected or not self.reader:
            return None

        try:
            data = await self.reader.read(1024)
            if not data:
                LOGGER.warning("Connection closed by peer")
                self.is_connected = False
                return None
            return data
        except ConnectionResetError:
            LOGGER.error("Connection reset while receiving")
            self.is_connected = False
            return None
        except Exception as e:
            LOGGER.error(f"Receive error: {e}")
            self.is_connected = False
            return None


async def test_connection(host: str, port: Optional[int] = None, timeout: int = 5) -> bool:
    """Test the connection with a timeout."""
    connection = RS485Connection(host, port)
    try:
        await asyncio.wait_for(connection.connect(), timeout=timeout)
        
        if connection.is_connected:
            LOGGER.info("Connection test successful.")
            return True
        else:
            LOGGER.error("Connection test failed.")
            return False
    except asyncio.TimeoutError:
        LOGGER.error("Connection test timed out.")
        return False
    except Exception as e:
        LOGGER.error(f"Connection test failed with error: {e}")
        return False
    finally:
        await connection.disconnect()
