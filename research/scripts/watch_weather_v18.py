import asyncio
import struct
import sys
import time
from bleak import BleakClient, BleakError

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Binding Handshake
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

client_ref = None
pid_counter = 0

def build_master_packet(i: int, i2: int, opcode: int, payload: bytes) -> list[bytes]:
    global pid_counter
    length = len(payload)
    if length <= 10:
        pkt = bytearray(20)
        pkt[0] = 0x00
        pkt[1] = pid_counter & 0xFF
        pkt[2] = 0x00
        pkt[3] = i & 0xFF
        pkt[4] = i2 & 0xFF
        pkt[5] = opcode & 0xFF
        pkt[8:10] = struct.pack("<H", length)
        pkt[10:10+length] = payload
        pid_counter = (pid_counter + 1) % 256
        return [bytes(pkt)]
    else:
        remaining = length - 10
        add_frags = remaining // 19 + (1 if remaining % 19 > 0 else 0)
        total_size = (add_frags * 20) + 20
        buffer = bytearray(total_size)
        buffer[0] = 0x00
        buffer[1] = pid_counter & 0xFF
        buffer[2] = add_frags & 0xFF
        buffer[3] = i & 0xFF
        buffer[4] = i2 & 0xFF
        buffer[5] = opcode & 0xFF
        buffer[8:10] = struct.pack("<H", length)
        buffer[10:20] = payload[:10]
        for f in range(add_frags):
            offset = (f + 1) * 20
            buffer[offset] = f + 1
            start = 10 + (f * 19)
            end = min(start + 19, length)
            buffer[offset + 1 : offset + 1 + (end - start)] = payload[start : end]
        pid_counter = (pid_counter + 1) % 256
        return [bytes(buffer[idx:idx+20]) for idx in range(0, total_size, 20)]

def get_time_sync_payload() -> bytes:
    return struct.pack("<IIB", int(time.time()), 7200, 0x01)

def get_weather_payload(w_type: int, cur: int, high: int, low: int, hum: int, wind: int) -> bytes:
    # Type(b), Cur(h), High(h), Low(h), Hum(b), Wind(b)
    return struct.pack("<bhhhbB", w_type, cur, high, low, hum, wind)

async def send_command(chunks: list[bytes], label: str):
    for idx, chunk in enumerate(chunks):
        await client_ref.write_gatt_char(WRITE_UUID, chunk, response=False)
        print(f"[>] Sent {label} (Chunk {idx})")

async def telemetry_handler(sender, data: bytearray):
    if len(data) >= 3 and data[0] == 0x00 and data[2] == 0x0C:
        print("[!] Sync Request. Replying...")
        await send_command(build_master_packet(0, 1, 0x0C, get_time_sync_payload()), "Time Sync")

async def main():
    global client_ref
    async with BleakClient(MAC_ADDRESS) as client:
        client_ref = client
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
        await asyncio.sleep(2)
        
        # Push weather: Sunny(0), 18C, High 22, Low 12, 60% Hum, 15km/h
        weather_payload = get_weather_payload(0, 18, 22, 12, 60, 15)
        await send_command(build_master_packet(0, 1, 0x94, weather_payload), "Weather Update")
        
        print("[+] Weather pushed. Keeping connection for 5s...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
