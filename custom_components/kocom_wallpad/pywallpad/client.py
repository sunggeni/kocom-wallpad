"""Client for py wallpad."""

from __future__ import annotations

import asyncio
from queue import Queue
from typing import Callable, Optional

from ..connection import Connection

from .crc import verify_checksum
from .packet import PacketParser
from .const  import _LOGGER


class PacketQueue:
    """Manages the queue for packet transmission."""

    def __init__(self):
        self._queue = Queue()
        self._pause = asyncio.Event()
        self._pause.set()  # Initially not paused
        self._has_items = asyncio.Event()

    def add_packet(self, packet: bytes):
        """Add a packet to the queue."""
        self._queue.put(packet)
        self._has_items.set()

    def get_packet(self) -> Optional[bytes]:
        """Get a packet from the queue."""
        try:
            packet = self._queue.get_nowait()
            if self._queue.empty():
                self._has_items.clear()  # Reset if the queue is empty
            return packet
        except Exception:
            return None

    async def pause(self):
        """Pause the queue processing."""
        self._pause.clear()

    async def resume(self):
        """Resume the queue processing."""
        self._pause.set()

    async def wait_for_packet(self):
        """Wait until there is a packet in the queue."""
        await self._has_items.wait()

    async def wait_for_resume(self):
        """Wait until the queue is resumed."""
        await self._pause.wait()


class KocomClient:
    """Client for the Kocom Wallpad."""

    def __init__(self, connection: Connection, timeout = 1.2, max_retries = 3) -> None:
        """Initialize the KocomClient."""
        self.timeout = timeout
        self.max_retries = max_retries

        self.connection = connection
        self.tasks: list[asyncio.Task] = []
        self.device_callbacks: list[Callable] = []
        self.packet_queue = PacketQueue()

    async def start(self) -> None:
        """Start the client."""
        _LOGGER.debug("Starting client...")
        self.tasks.append(asyncio.create_task(self._listen()))
        self.tasks.append(asyncio.create_task(self._process_queue()))

    async def stop(self) -> None:
        """Stop the client."""
        _LOGGER.debug("Stopping client...")
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()
        self.device_callbacks.clear()

    def add_device_callback(self, callback: Callable) -> None:
        """Add callback for device updates."""
        self.device_callbacks.append(callback)

    async def _listen(self) -> None:
        """Listen for incoming packets."""
        while self.connection.is_connected():
            try:
                receive_data = await self.connection.receive()
                if receive_data is None:
                    continue
                
                packets = self.extract_packets(receive_data)
                for packet in packets:
                    if not verify_checksum(packet):
                        _LOGGER.debug("Checksum verification failed for packet: %s", packet.hex())
                        continue
                    
                    parsed_packet = PacketParser.parse_state(packet.hex())
                    for parse_packet in parsed_packet:
                        for callback in self.device_callbacks:
                            await callback(parse_packet)
            except Exception as e:
                _LOGGER.error(f"Error receiving data: {e}", exc_info=True)
    
    def extract_packets(self, data: bytes) -> list[bytes]:
        """Extract packets from the received data."""
        packets: list[bytes] = []
        start = 0

        while start < len(data):
            start_pos = data.find(b'\xaa\x55', start)
            if start_pos == -1:
                break

            end_pos = data.find(b'\x0d\x0d', start_pos + len(b'\xaa\x55'))
            if end_pos == -1:
                break

            packet = data[start_pos:end_pos + len(b'\x0d\x0d')]
            packets.append(packet)

            start = end_pos + len(b'\x0d\x0d')

        return packets
    
    async def _process_queue(self) -> None:
        """Process packets in the queue."""
        while self.connection.is_connected():
            await asyncio.gather(
                self.packet_queue.wait_for_packet(),
                self.packet_queue.wait_for_resume(),
            )

            packet = self.packet_queue.get_packet()
            if packet:
                retries = 0
                while retries < self.max_retries:
                    try:
                        _LOGGER.debug(f"Sending packet: {packet.hex()}, Retries: {retries}")
                        await self.connection.send(packet)
                        break
                    except Exception as e:
                        retries += 1
                        _LOGGER.error(f"Send error: {e}. Retry {retries}/{self.max_retries}")
                        await asyncio.sleep(self.timeout)
                else:
                    _LOGGER.error(f"Max retries reached for packet: {packet.hex()}")

    async def send(self, packet: bytes) -> None:
        """Send a packet to the device."""
        self.packet_queue.add_packet(packet)
