import asyncio
import struct
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"  # Your watch MAC
WRITE_UUID   = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID  = "0000b001-0000-1000-8000-00805f9b34fb"

OPCODES = {
    0x04: "Firmware & App Version Info",
    0x08: "Device Hardware Settings",
    0x0B: "Model & Device Identification",
    0x66: "User Profile Configuration",
    0x67: "Hardware Feature Flags",
    0x6D: "Activity & Sensor Status",
    0x78: "Pairing Master Handshake",
    0x80: "Heart Rate Telemetry",
}

def build_packet(opcode: int, payload: bytes = b"") -> bytes:
    """Builds outgoing app-to-device command packets."""
    total_length = len(payload) + 3
    return struct.pack("<H", total_length) + bytes([opcode]) + payload

def smart_notification_handler(sender, data: bytearray):
    """
    Intelligently decodes incoming 20-byte MTU telemetry frames.
    """
    if len(data) < 5:
        return

    # Check if this frame uses the 00FF MTU header wrapping
    if data[0] == 0x00 and data[1] == 0xFF:
        seq_flags = struct.unpack("<H", data[2:4])[0]
        opcode = data[4]
        payload = data[5:]
        frame_type = "MTU Wrapped (0x00FF)"
    else:
        # Fallback to standard app-style packet slicing
        opcode = data[2]
        payload = data[3:]
        frame_type = "Standard GATT"

    opcode_name = OPCODES.get(opcode, f"Unknown (0x{opcode:02X})")
    
    print(f"\n[<<< TELEMETRY RECEIVED] {opcode_name} (Opcode: 0x{opcode:02X})")
    print(f"  ├── Frame Format: {frame_type}")
    print(f"  ├── Raw Payload:  {payload.hex()}")

    # --- Specific Decoder Logic for Known Opcodes ---
    if opcode == 0x04 and len(payload) >= 6:
        # Decode firmware version string from sequential bytes
        v1, v2, v3, v4 = payload[2], payload[3], payload[4], payload[5]
        print(f"  └── Decoded Info: Firmware Build v{v1}.{v2}.{v3}.{v4}")
        
    elif opcode == 0x0B:
        try:
            model_str = payload.decode("utf-8", errors="ignore").rstrip("\x00").strip()
            print(f"  └── Decoded Info: Device Model -> '{model_str}'")
        except Exception:
            pass
            
    elif opcode == 0x6D and len(payload) >= 4:
        # Byte index 4 in sensor reports usually maps to battery percentage
        battery = payload[3] if len(payload) > 3 else "N/A"
        print(f"  └── Decoded Info: Battery Level ~ {battery}% | Sensor Status: Active")

async def main():
    print(f"[*] Connecting to {MAC_ADDRESS}...")
    async with BleakClient(MAC_ADDRESS, timeout=15.0) as client:
        if not client.is_connected:
            return
            
        print("[+] Link active. Biding notification channel...")
        await client.start_notify(NOTIFY_UUID, smart_notification_handler)
        await asyncio.sleep(0.5)

        print("[>] Executing Master Handshake (0x78)...")
        await client.write_gatt_char(WRITE_UUID, build_packet(0x78, b"\x01\x00"), response=False)
        await asyncio.sleep(1.0)

        print("[>] Stabilizing RTC Clock (0x68)...")
        await client.write_gatt_char(WRITE_UUID, build_packet(0x68, bytes.fromhex("48ff536a201c00020000")), response=False)
        await asyncio.sleep(1.0)

        # We increase the sleep duration to 2.5s and test explicit read/query flags
        queries = [
            (0x04, b"\x01"),         # Firmware Version
            (0x0B, b"\x01\x00"),     # Model ID (with extended read flag)
            (0x6D, b"\x01"),         # Battery / Sensor Status
            (0x67, b"\x01\x00"),     # Feature Flags
        ]
        
        for opcode, test_payload in queries:
            print(f"\n[?] Querying {OPCODES.get(opcode, hex(opcode))}...")
            await client.write_gatt_char(WRITE_UUID, build_packet(0, test_payload) if opcode == 0 else build_packet(opcode, test_payload), response=False)
            await asyncio.sleep(2.5) # Give the watch MCU ample time to respond

        print("\n[*] Query sweep complete. Listening for delayed frames...")
        await asyncio.sleep(4.0)
        await client.stop_notify(NOTIFY_UUID)

if __name__ == "__main__":
    asyncio.run(main())
