"""Utilities for Kocom Wallpad."""

from __future__ import annotations

def create_dev_id(
    device_type: str, room_id: str | None, sub_id: str | None
) -> str:
    """Create a device ID."""
    return "_".join(filter(None, [device_type, room_id, sub_id]))
