"""Client for py wallpad."""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Awaitable
from dataclasses import dataclass

from ..connection import RS485Connection
from .crc import (
    verify_checksum,
    verify_crc,
    calculate_checksum,
    calculate_crc,
)
from .packet import (
    KocomPacket,
    PacketParser,
    DoorPhoneParser,
)
from .const import _LOGGER, PREFIX_HEADER, SUFFIX_HEADER


@dataclass
class PacketQueue:
    """A queue of packets to be sent."""
    packet: bytearray
    retries: int = 0


class KocomClient:
    """Client for the Kocom Wallpad."""

    def __init__(self, connection: RS485Connection) -> None:
        """Initialize the KocomClient."""
        self.connection = connection
        self.packet_length = 21
        self.max_buffer_size = 4096
        self.buffer = bytes()
        self.max_retries = 4

        self.tasks: list[asyncio.Task] = []
        self.device_callbacks: list[Callable[[KocomPacket], Awaitable[None]]] = []
        self.packet_queue: asyncio.Queue[PacketQueue] = asyncio.Queue()
        self.last_packet: KocomPacket | None = None
        #self.packet_lock: asyncio.Lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the client."""
        _LOGGER.debug("Starting Kocom Client...")
        self.tasks.append(asyncio.create_task(self.connection.reconnect_manager()))
        self.tasks.append(asyncio.create_task(self._listen()))
        self.tasks.append(asyncio.create_task(self._process_queue()))

    async def stop(self) -> None:
        """Stop the client."""
        _LOGGER.debug("Stopping Kocom Client...")
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()
        self.device_callbacks.clear()
        self.last_packet = None

    def add_device_callback(self, callback: Callable[[KocomPacket], Awaitable[None]]) -> None:
        """Add callback for device updates."""
        self.device_callbacks.append(callback)

    async def _listen(self) -> None:
        """Listen for incoming packets."""
        while True:
            try:
                if not self.connection.is_connected:
                    await asyncio.sleep(1)
                    continue

                receive_data = await self.connection.receive()
                if not receive_data:
                    await asyncio.sleep(1)
                    continue

                for packet in self.extract_packets(receive_data):
                    await self._process_packet(packet)
                    
            except ValueError as ve:
                _LOGGER.error(f"Error processing packet: {ve}", exc_info=True)
                await asyncio.sleep(1)
            except Exception as e:
                _LOGGER.error(f"Error receiving data: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_packet(self, packet: bytes) -> None:
        """Process a single packet."""
        parser, log_message = None, None

        if verify_checksum(packet):
            parser, log_message = PacketParser, "Received packet"
        elif verify_crc(packet):
            parser, log_message = DoorPhoneParser, "Received door phone"
        else:
            _LOGGER.debug(f"Invalid packet received: {packet.hex()}")
            return

        if parser:
            parsed_packets = parser.parse_state(packet)
            for parsed_packet in parsed_packets:
                _LOGGER.debug(
                    f"{log_message}: {parsed_packet}, {parsed_packet._device}, {parsed_packet._last_data}"
                )
                if isinstance(parsed_packet, KocomPacket):
                    #async with self.packet_lock:
                        self.last_packet = parsed_packet
                    #    _LOGGER.debug(f"Updated last packet: {parsed_packet}")

                if parsed_packet._device is None:
                    continue

                for callback in self.device_callbacks:
                    try:
                        await callback(parsed_packet)
                    except Exception as e:
                        _LOGGER.error(f"Error in callback: {e}", exc_info=True)

    async def _process_queue(self) -> None:
        """Process packets in the queue."""
        while True:
            try:
                queue = await self.packet_queue.get()
                _LOGGER.debug(f"Sending packet: {queue.packet.hex()}")
                await self.connection.send(queue.packet)

                if verify_crc(queue.packet):
                    self.packet_queue.task_done()
                    continue

                try:
                    packet = KocomPacket(queue.packet)
                    found_match = False
                    start_time = time.time()
                    
                    while (time.time() - start_time) < 1.0:
                        #async with self.packet_lock:
                        if self.last_packet is None:
                            await asyncio.sleep(0.1)
                            continue

                        if (self.last_packet.device_id == packet.device_id and
                            self.last_packet.sequence == packet.sequence and
                            self.last_packet.dest == packet.src and 
                            self.last_packet.src == packet.dest):
                            found_match = True
                            self.last_packet = None
                            break

                        await asyncio.sleep(0.1)

                    if not found_match:
                        _LOGGER.debug("not received ack retrying..")
                        await self._handle_retry(queue)
                    else:
                        _LOGGER.debug(f"Command success: {queue.packet.hex()}")
                        self.packet_queue.task_done()

                except Exception as e:
                    _LOGGER.error(f"Error processing response: {e}", exc_info=True)
                    await self._handle_retry(queue)
        
            except Exception as e:
                _LOGGER.error(f"Error processing queue: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _handle_retry(self, queue: PacketQueue) -> None:
        """Handle command retry."""
        if queue.retries >= self.max_retries:
            _LOGGER.error(f"Command failed after {self.max_retries} retries: {queue.packet.hex()}")
            self.packet_queue.task_done()
            return

        queue.retries += 1
        _LOGGER.debug(f"Retrying command (attempt {queue.retries}): {queue.packet.hex()}")
        await asyncio.sleep(0.12 * (2 ** queue.retries))
        await self.packet_queue.put(queue)

    def extract_packets(self, data: bytes) -> list[bytes]:
        """Extract packets from the received data."""
        self.buffer += data
        packets: list[bytes] = []

        while len(self.buffer) >= self.packet_length:
            start_pos = self.buffer.find(PREFIX_HEADER)
            if start_pos == -1:
                self.buffer = bytes()
                break

            if start_pos > 0:
                self.buffer = self.buffer[start_pos:]

            if len(self.buffer) < self.packet_length:
                break

            if self.buffer[self.packet_length - 2:self.packet_length] != SUFFIX_HEADER:
                self.buffer = self.buffer[2:]
                continue

            packet = self.buffer[:self.packet_length]
            packets.append(packet)

            self.buffer = self.buffer[self.packet_length:]

        if len(self.buffer) > self.max_buffer_size:
            self.buffer = self.buffer[-self.max_buffer_size:]

        return packets

    async def send_packet(self, packet: bytearray | list[tuple[bytearray, float | None]]) -> None:
        """Send a packet to the device."""
        if isinstance(packet, list):
            for p, delay in packet:
                if delay is not None:
                    await asyncio.sleep(delay)

                p[:0] = PREFIX_HEADER
                if (crc := calculate_crc(p)) is None:
                    _LOGGER.error(f"Failed to calculate checksum for packet: {p.hex()}")
                    continue
                
                p.extend(crc)
                p.extend(SUFFIX_HEADER)

                if not verify_crc(p):
                    _LOGGER.error(f"Failed to verify checksum for packet: {p.hex()}")
                    continue

                queue = PacketQueue(packet=p)
                await self.packet_queue.put(queue)
        else:
            packet[:0] = PREFIX_HEADER
            if (sum := calculate_checksum(packet)) is None:
                _LOGGER.error(f"Failed to calculate checksum for packet: {packet.hex()}")
                return
            
            packet.append(sum)
            packet.extend(SUFFIX_HEADER)

            if not verify_checksum(packet):
                _LOGGER.error(f"Failed to verify checksum for packet: {packet.hex()}")
                return
        
            queue = PacketQueue(packet=packet)
            await self.packet_queue.put(queue)
