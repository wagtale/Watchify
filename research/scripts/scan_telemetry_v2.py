import asyncio
import struct
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"  # Your watch MAC
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Async lock to synchronize TX loop with RX radio arrivals
response_event = asyncio.Event()
current_testing_opcode = 0
discovered_registers = {}

def build_packet(opcode: int, payload: bytes = b"") -> bytes:
    total_length = len(payload) + 3
    return struct.pack("<H", total_length) + bytes([opcode]) + payload

def sync_notification_handler(sender, data: bytearray):
    if len(data) < 6:
        return

    # Check for ZebraKing MTU wrapping (0x00FF)
    if data[0] == 0x00 and data[1] == 0xFF:
        # Byte index 4 is the Direction Flag (0x04). Byte index 5 is the TRUE OPCODE!
        direction_flag = data[4]
        true_opcode = data[5]
        payload = data[6:]
    else:
        true_opcode = data[2] if len(data) > 2 else 0
        payload = data[3:] if len(data) > 3 else b""

    # Log the confirmed discovery
    if true_opcode not in discovered_registers:
        discovered_registers[true_opcode] = []
    discovered_registers[true_opcode].append(payload.hex())

    print(f"\n[!!! CONFIRMED HIT !!!] Opcode 0x{true_opcode:02X} (Dec: {true_opcode}) responded!")
    print(f"  ├── Direction Flag: 0x{data[4]:02X}")
    print(f"  ├── Raw Payload:    {payload.hex()}")
    
    try:
        ascii_str = payload.decode("utf-8", errors="ignore").rstrip("\x00").strip()
        if any(c.isalnum() for c in ascii_str) and len(ascii_str) > 0:
            print(f"  └── ASCII Decode:   '{ascii_str}'")
    except Exception:
        pass

    # Unlock the TX loop so it can proceed to the next opcode
    response_event.set()

async def main():
    global current_testing_opcode
    print(f"[*] Initializing Precision Synchronized Scanner on [{MAC_ADDRESS}]...")
    
    async with BleakClient(MAC_ADDRESS, timeout=15.0) as client:
        if not client.is_connected:
            return
            
        print("[+] Link active. Binding notification channel...")
        await client.start_notify(NOTIFY_UUID, sync_notification_handler)
        await asyncio.sleep(0.5)

        print("[>] Executing Master Handshake (0x78)...")
        await client.write_gatt_char(WRITE_UUID, build_packet(0x78, b"\x01\x00"), response=False)
        await asyncio.sleep(1.0)

        print("[>] Stabilizing RTC Clock (0x68)...")
        await client.write_gatt_char(WRITE_UUID, build_packet(0x68, bytes.fromhex("48ff536a201c00020000")), response=False)
        await asyncio.sleep(1.0)

        print("\n--- [ Precision Sweep: Opcodes 0x60 to 0x8F (Read Flag b'\\x00') ] ---")
        for opcode in range(0x60, 0x90):
            current_testing_opcode = opcode
            print(f"\r[*] Testing Opcode: 0x{opcode:02X} (Dec: {opcode})...", end="", flush=True)
            
            response_event.clear()
            await client.write_gatt_char(WRITE_UUID, build_packet(opcode, b"\x00"), response=False)
            
            # Wait up to 1.8 seconds for the watch radio queue to respond before timing out
            try:
                await asyncio.wait_for(response_event.wait(), timeout=1.8)
            except asyncio.TimeoutError:
                pass # No response from this register; move on cleanly
            
            await asyncio.sleep(0.1) # Small buffer between RF bursts

        await client.stop_notify(NOTIFY_UUID)

    print("\n\n=======================================================")
    print("      PRECISION SYNCHRONIZED HARDWARE MAP              ")
    print("=======================================================")
    for op, hex_list in sorted(discovered_registers.items()):
        print(f"  * Opcode 0x{op:02X} (Dec {op:<3}) -> Payload: {hex_list[0]}")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(main())
