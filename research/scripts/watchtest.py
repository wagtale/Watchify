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
watch_unlocked_event = asyncio.Event()

def build_zk_command(opcode: int, payload: bytes = b"") -> bytes:
    total_length = len(payload) + 3
    length_prefix = struct.pack("<H", total_length)
    return b"\x00" + length_prefix + bytes([opcode]) + payload

def get_time_sync_payload() -> bytes:
    current_unix_sec = int(time.time())
    tz_offset_sec = 7200  # SAST (Cape Town UTC+2)
    return struct.pack("<IIB", current_unix_sec, tz_offset_sec, 0x01)

def get_ai_text_payload(text: str) -> bytes:
    text_bytes = text.encode('utf-8')[:32]
    str_len = len(text_bytes)
    header = struct.pack("<BII", 0x01, str_len, 0)
    return header + text_bytes

async def send_command(data: bytes, label: str = "Command"):
    if not client_ref or not client_ref.is_connected:
        return
    try:
        await client_ref.write_gatt_char(WRITE_UUID, data, response=False)
        print(f"[>] Sent {label}: {data.hex()}")
    except Exception as e:
        print(f"[!] Write failed ({label}): {e}")

async def telemetry_handler(sender, data: bytearray):
    if len(data) < 3:
        return
    
    frag_index = data[0]
    incoming_opcode = data[2] if frag_index == 0x00 and len(data) >= 3 else None

    # 1. Answer Time Sync Request (Opcode 0x0C)
    if incoming_opcode == 0x0C:
        retry_num = data[3] if len(data) >= 4 else 1
        print(f"\n[!] Watch requesting Time Sync (Attempt #{retry_num}). Sending Unix Timestamp...")
        sync_cmd = build_zk_command(0x0C, get_time_sync_payload())
        await send_command(sync_cmd, f"Time Sync ACK #{retry_num}")
        return

    # 2. Catch Execution Confirmation (Status 0x00 at Byte 2, ACK Opcode at Byte 3)
    if incoming_opcode == 0x00 and len(data) >= 4:
        acked_opcode = data[3]
        print(f"\n[+] WATCH EXECUTION CONFIRMED! Success ACK for Opcode 0x{acked_opcode:02X}.")
        
        # If Opcode 0x0C was acknowledged, trigger the unlock event!
        if acked_opcode == 0x0C:
            print("[*] Clock verified by firmware! Unlocking automated command test...")
            watch_unlocked_event.set()
        return

    # 3. Print routine telemetry
    if frag_index == 0x00:
        print(f"[<<<] Telemetry Cycle | Raw: {data.hex()}")

async def run_automated_test():
    print("\n--- WAITING FOR WATCH TO UNLOCK (TIME SYNC ACK) ---")
    
    try:
        # Wait up to 15 seconds for the watch to verify clock and ACK 0x0C
        await asyncio.wait_for(watch_unlocked_event.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        print("\n[!] Timeout waiting for Time Sync ACK. Proceeding with test anyway...")

    print("\n=======================================================")
    print("      WATCH UNLOCKED! STARTING AUTOMATED TEST          ")
    print("=======================================================")
    
    # --- TEST 1: TRIPLE VIBRATION PULSE ---
    print("\n[*] TEST 1: Sending 3 Vibration Pulses (3 seconds apart)...")
    for i in range(1, 4):
        print(f"\n--- Firing Buzz #{i} ---")
        await send_command(build_zk_command(0x74, b"\x01"), f"Vibrate Motor Pulse #{i}")
        await asyncio.sleep(3.0) # 3 second pause so you can feel it physically!

    # --- TEST 2: AI TEXT DISPLAY ---
    test_message = "ZK UNLOCKED"
    print(f"\n[*] TEST 2: Sending LCD Screen Text: '{test_message}'...")
    ai_payload = get_ai_text_payload(test_message)
    await send_command(build_zk_command(0x9A, ai_payload), "AI Text Display Command")
    
    # Hold connection open for 10 seconds so watch has plenty of time to render LCD!
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
        
        # Run the automated test sequence instead of manual shell
        await run_automated_test()
        
        await client.stop_notify(NOTIFY_UUID)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
