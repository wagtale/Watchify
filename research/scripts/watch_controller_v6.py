import asyncio
import struct
from datetime import datetime
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

client_ref = None
seq_counter = 0

def calculate_crc16(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x8005
            else: crc <<= 1
            crc &= 0xFFFF
    return crc

def build_secure_packet(opcode: int, payload: bytes = b"") -> bytes:
    global seq_counter
    # Header: [Len(2)] + [Seq(1)] + [Opcode(1)] + [Payload]
    seq = bytes([seq_counter % 256])
    body = seq + bytes([opcode]) + payload
    length_prefix = struct.pack("<H", len(body) + 2)
    crc = calculate_crc16(body)
    seq_counter += 1
    return length_prefix + body + struct.pack("<H", crc)

async def send_command(data: bytes, label: str = "Command"):
    if client_ref:
        await client_ref.write_gatt_char(WRITE_UUID, data, response=False)
        print(f"[>] Sent {label} (Opcode: 0x{data[3]:02X}, Seq: {data[2]})")

async def telemetry_handler(sender, data: bytearray):
    if len(data) < 3: return
    opcode = data[3] # Adjusted index for new header
    
    if opcode == 0x0C:
        print("\n[!] Watch requesting Sync. Sending Sequenced Sync...")
        await send_command(build_secure_packet(0x0C, b"\x01\x01\x01\x01\x01\x01"), "Sequenced Sync")
    
    print(f"\n[<<<] Opcode 0x{opcode:02X}")

async def interactive_shell():
    loop = asyncio.get_event_loop()
    while True:
        user_input = await loop.run_in_executor(None, input, "WatchCmd > ")
        if not user_input.strip(): continue # Fixes the crash
        parts = user_input.split()
        cmd = parts[0]
        if cmd == "text": await send_command(build_secure_packet(0x9A, parts[1].encode()), "Text")
        elif cmd == "exit": break

async def main():
    global client_ref
    async with BleakClient(MAC_ADDRESS) as client:
        client_ref = client
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await send_command(FULL_BIND_PAYLOAD, "Handshake")
        await interactive_shell()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\n[!] Exiting...")
