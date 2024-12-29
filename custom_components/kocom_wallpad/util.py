"""Utilities for Kocom Wallpad."""

from __future__ import annotations

import base64
import json

def create_dev_id(
    device_type: str, room_id: str | None, sub_id: str | None
) -> str:
    """Create a device ID."""
    return "_".join(filter(None, [device_type, room_id, sub_id]))

def encode_bytes_to_base64(data: bytes) -> str:
    """Encode bytes to Base64 string."""
    return base64.b64encode(data).decode("utf-8")

def decode_base64_to_bytes(data: str) -> bytes:
    """Decode Base64 string to bytes."""
    return base64.b64decode(data)
