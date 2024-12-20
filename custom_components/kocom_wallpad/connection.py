"""Connection class for Kocom Wallpad."""

from __future__ import annotations

from typing import Optional
import time
import asyncio

from .const import LOGGER

MAX_READ_BYTES = 256


class Connection:
    """Handles gateway connections."""
    
    def __init__(self, host: str, port: int) -> None:
        """Initialize the Connection."""
        self.host: str = host
        self.port: int = port

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.reconnect_attempts: int = 0
        self.last_reconnect_attempt: Optional[float] = None
        self.next_attempt_time: Optional[float] = None

    async def connect(self):
        """Establish a connection."""
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            self.reconnect_attempts = 0
            LOGGER.info(f"Connection established to {self.host}:{self.port}")
        except Exception as e:
            LOGGER.error(f"Connection failed: {e}")
            await self.reconnect()

    def is_connected(self) -> bool:
        """Check if the connection is active."""
        return self.writer is not None and not self.writer.is_closing()

    async def reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()

        current_time = time.time()
        if self.next_attempt_time and current_time < self.next_attempt_time:
            LOGGER.info(f"Waiting for {self.next_attempt_time - current_time} seconds before next reconnection attempt.")
            return
        
        self.reconnect_attempts += 1
        delay = min(2 ** self.reconnect_attempts, 60) if self.last_reconnect_attempt else 1
        self.last_reconnect_attempt = current_time
        self.next_attempt_time = current_time + delay
        LOGGER.info(f"Reconnection attempt {self.reconnect_attempts} after {delay} seconds delay...")

        await asyncio.sleep(delay)
        await self.connect()
        if self.is_connected():
            LOGGER.info(f"Successfully reconnected on attempt {self.reconnect_attempts}.")
            self.reconnect_attempts = 0
            self.next_attempt_time = None

    async def send(self, packet: bytearray):
        """Send a packet."""
        try:
            self.writer.write(packet)
            await self.writer.drain()
            await asyncio.sleep(0.1)
        except Exception as e:
            LOGGER.error(f"Failed to send packet data: {e}")
            await self.reconnect()

    async def receive(self) -> Optional[bytes]:
        """Receive data."""
        try:
            return await self.reader.read(MAX_READ_BYTES)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            LOGGER.error(f"Failed to receive packet data: {e}")
            await self.reconnect()
            return None
    
    async def close(self):
        """Close the connection."""
        if self.writer:
            LOGGER.info("Connection closed.")
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None
