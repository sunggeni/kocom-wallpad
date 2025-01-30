"""CRC calculation for py wallpad."""

def crc_ccitt_xmodem(data: bytes) -> int:
    """Calculate CRC-CCITT (XMODEM) checksum."""
    crc = 0x0000
    polynomial = 0x1021

    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ polynomial
            else:
                crc = crc << 1
            crc &= 0xFFFF  # Keep CRC 16-bit
    return crc

def verify_crc(packet: bytes) -> bool:
    """Verify CRC for a packet."""
    if len(packet) < 21:
        return False

    data = packet[2:17]  # Data for CRC calculation (bytes 3 to 17, 0-indexed)
    provided_checksum = (packet[17] << 8) | packet[18]  # Combine two bytes for the provided checksum

    calculated_checksum = crc_ccitt_xmodem(data)
    return calculated_checksum == provided_checksum

def calculate_crc(packet: bytes) -> list[int, int] | None:
    """Calculate CRC for a packet."""
    if len(packet) < 17:
        return None
    
    data = packet[2:17]  # Data for CRC calculation (bytes 3 to 17, 0-indexed)
    checksum = crc_ccitt_xmodem(data)

    # Append the 16-bit checksum (split into two bytes)
    checksum_high = (checksum >> 8) & 0xFF
    checksum_low = checksum & 0xFF
    return [checksum_high, checksum_low]

def verify_checksum(packet: bytes) -> bool:
    """Verify checksum for a packet."""
    packet_checksum = packet[-3]
    data_to_sum = packet[:-3]
    sum_val = sum(data_to_sum) & 0xFF
    calc_checksum = (sum_val + 1) & 0xFF
    return (calc_checksum == packet_checksum)

def calculate_checksum(packet: bytes) -> int | None:
    """Calculate checksum for a packet."""
    sum_val = sum(packet) & 0xFF    
    checksum = (sum_val + 1) & 0xFF
    return checksum
