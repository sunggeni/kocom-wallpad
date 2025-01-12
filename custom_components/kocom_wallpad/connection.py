from __future__ import annotations

from typing import Optional
import asyncio

from .const import LOGGER


class RS485Connection:
    """Connection class for RS485 communication with read lock protection."""

    def __init__(self, host: str, port: int):
        """Initialize the connection."""
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.is_connected = False
        self.reconnect_interval = 5
        self._running = True

    async def connect(self) -> bool:
        """Connect to the device."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            self.is_connected = True
            LOGGER.info(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            LOGGER.error(f"Socket connection failed: {e}")
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
        """Receive data from the device with read lock protection."""
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


async def test_connection(host: str, port: int, timeout: int = 5) -> bool:
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
