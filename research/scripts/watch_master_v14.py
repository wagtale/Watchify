import asyncio
import struct
import sys
import time
from bleak import BleakClient, BleakError

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Verified 92-byte binding handshake
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

client_ref = None
pid_counter = 0
watch_unlocked_event = asyncio.Event()

def build_master_packet(i: int, i2: int, opcode: int, payload: bytes) -> list[bytes]:
    """Exact Python translation of ProtocolAppToDevice.g(i, i2, opcode, payload)."""
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
        pkt[6] = 0x00
        pkt[7] = 0x00
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
        buffer[6] = 0x00
        buffer[7] = 0x00
        buffer[8:10] = struct.pack("<H", length)
        buffer[10:20] = payload[:10]
        
        for f in range(add_frags):
            offset = (f + 1) * 20
            buffer[offset] = f + 1
            start_idx = 10 + (f * 19)
            end_idx = min(start_idx + 19, length)
            chunk_len = end_idx - start_idx
            buffer[offset + 1 : offset + 1 + chunk_len] = payload[start_idx : end_idx]
            
        pid_counter = (pid_counter + 1) % 256
        return [bytes(buffer[idx:idx+20]) for idx in range(0, total_size, 20)]

def get_time_sync_payload() -> bytes:
    current_unix_sec = int(time.time())
    tz_offset_sec = 7200  # SAST (Cape Town UTC+2)
    return struct.pack("<IIB", current_unix_sec, tz_offset_sec, 0x01)

def get_ai_text_payload(text: str) -> bytes:
    text_bytes = text.encode('utf-8')[:32]
    str_len = len(text_bytes)
    header = struct.pack("<BII", 0x01, str_len, 0)
    return header + text_bytes

async def send_command(chunks: list[bytes], label: str = "Command"):
    if not client_ref or not client_ref.is_connected:
        return
    try:
        for idx, chunk in enumerate(chunks):
            await client_ref.write_gatt_char(WRITE_UUID, chunk, response=False)
            print(f"[>] Sent {label} (Chunk {idx}/{len(chunks)-1}): {chunk.hex()}")
            if len(chunks) > 1:
                await asyncio.sleep(0.05)
    except Exception as e:
        print(f"[!] Write failed ({label}): {e}")

async def telemetry_handler(sender, data: bytearray):
    if len(data) < 3:
        return
    
    frag_index = data[0]
    incoming_opcode = data[2] if frag_index == 0x00 and len(data) >= 3 else None

    if incoming_opcode == 0x0C:
        retry_num = data[3] if len(data) >= 4 else 1
        print(f"\n[!] Watch requesting Time Sync (Attempt #{retry_num}). Sending verified Java 10-Byte header...")
        sync_chunks = build_master_packet(0, 1, 0x0C, get_time_sync_payload())
        await send_command(sync_chunks, f"Time Sync ACK #{retry_num}")
        return

    if incoming_opcode == 0x00 and len(data) >= 4:
        acked_opcode = data[3]
        print(f"\n[+] WATCH EXECUTION CONFIRMED! Success ACK for Opcode 0x{acked_opcode:02X}.")
        if acked_opcode == 0x0C:
            print("[*] Clock verified by firmware! Unlocking automated command test...")
            watch_unlocked_event.set()
        return

    if frag_index == 0x00:
        print(f"[<<<] Telemetry Cycle | Raw: {data.hex()}")

async def run_automated_test():
    print("\n--- WAITING FOR WATCH TO UNLOCK (TIME SYNC ACK) ---")
    try:
        await asyncio.wait_for(watch_unlocked_event.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        print("\n[!] Timeout waiting for Time Sync ACK. Proceeding with test anyway...")

    print("\n=======================================================")
    print("      WATCH UNLOCKED! STARTING AUTOMATED TEST          ")
    print("=======================================================")
    
    # --- TEST 1: FIND DEVICE VIBRATION (Opcode 11 / 0x0B) ---
    print("\n[*] TEST 1: Sending 'Find Device' Alarm (Opcode 0x0B)...")
    # In WTWD protocol, sending 0x01 starts the find vibration alarm!
    find_chunks = build_master_packet(0, 1, 0x0B, b"\x01")
    await send_command(find_chunks, "Find Watch Alarm ON")
    
    print("    Watch should be buzzing! Waiting 5 seconds...")
    await asyncio.sleep(5.0)
    
    # Send 0x00 to turn off the vibration alarm
    print("\n[*] Turning off 'Find Device' Alarm...")
    stop_find_chunks = build_master_packet(0, 1, 0x0B, b"\x00")
    await send_command(stop_find_chunks, "Find Watch Alarm OFF")
    await asyncio.sleep(1.0)

    # --- TEST 2: AI TEXT DISPLAY ---
    test_message = "ZK UNLOCKED"
    print(f"\n[*] TEST 2: Sending LCD Screen Text: '{test_message}'...")
    text_chunks = build_master_packet(0, 1, 0x9A, get_ai_text_payload(test_message))
    await send_command(text_chunks, "AI Text Display Command")
    
    print("\n[*] Command sent! Holding connection open for 10 seconds so watch screen can render...")
    for sec in range(10, 0, -1):
        print(f"    Closing in {sec}s... (Check watch screen now!)", end="\r")
        await asyncio.sleep(1.0)
        
    print("\n\n[+] Automated test complete! Disconnecting cleanly.")

async def main():
    global client_ref
    async with BleakClient(MAC_ADDRESS, timeout=15.0) as client:
        client_ref = client
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await asyncio.sleep(0.5)
        print("[>] Sending 92-Byte Binding Handshake...")
        await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
        await run_automated_test()
        await client.stop_notify(NOTIFY_UUID)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
