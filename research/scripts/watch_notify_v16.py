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

def get_notice_payload(app_id: int, text: str) -> bytes:
    """
    Implements ProtocolAppToDevice.k() for DATA_TYPE_MESSAGE_NOTICE (Opcode 107 / 0x6B):
    6-Byte Header:
      - Bytes 0-3: Unix Timestamp (4B LSB)
      - Byte 4   : Notice Category/Flag (0x01)
      - Byte 5   : Notification Count (0x01 for single item)
    Item Structure:
      - Byte 6   : App Icon ID (0=SMS, 7=WhatsApp, etc.)
      - Byte 7   : String Length in Bytes (1B)
      - Byte 8+  : UTF-8 Text Bytes
    """
    current_unix_sec = int(time.time())
    text_bytes = text.encode('utf-8')[:60]
    text_len = len(text_bytes)
    
    # 6-Byte Header: [Unix Time <I] + [Flag B] + [Count B]
    header = struct.pack("<IBB", current_unix_sec, 0x01, 0x01)
    
    # Item: [App ID B] + [Text Len B] + [Text Bytes]
    item = struct.pack("<BB", app_id & 0xFF, text_len & 0xFF) + text_bytes
    
    return header + item

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
            print("[*] Clock verified by firmware! Unlocking automated notification test...")
            watch_unlocked_event.set()
        return

    if frag_index == 0x00:
        print(f"[<<<] Telemetry Cycle | Raw: {data.hex()}")

def get_weather_payload(w_type: int, cur: int, high: int, low: int, hum: int, wind: int) -> bytes:
    """
    Builds the weather payload for Opcode 0x94 (DATA_TYPE_WEATHER).
    """
    # [Type 1B] + [Cur 2B] + [High 2B] + [Low 2B] + [Hum 1B] + [Wind 1B]
    return struct.pack("<bhhhbB", w_type, cur, high, low, hum, wind)

async def run_automated_test():
    print("\n--- WAITING FOR WATCH TO UNLOCK (TIME SYNC ACK) ---")
    try:
        await asyncio.wait_for(watch_unlocked_event.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        print("\n[!] Timeout waiting for Time Sync ACK. Proceeding with test anyway...")

    print("\n=======================================================")
    print("      WATCH UNLOCKED! STARTING NOTIFICATION TEST       ")
    print("=======================================================")
    
    # --- TEST 1: WHATSAPP POP-UP BANNER (Opcode 107 / 0x6B, App ID = 7) ---
    wa_text = "WhatsApp: BLE Push Working!"
    print(f"\n[*] TEST 1: Sending WhatsApp Push Notice (Opcode 0x6B, Icon=7): '{wa_text}'...")
    wa_payload = get_notice_payload(7, wa_text)
    wa_chunks = build_master_packet(0, 1, 0x6B, wa_payload)
    await send_command(wa_chunks, "WhatsApp Notification Banner")
    
    print("    Holding open 6 seconds for screen banner to display...")
    await asyncio.sleep(6.0)

    # --- TEST 2: SMS POP-UP BANNER (Opcode 107 / 0x6B, App ID = 0) ---
    sms_text = "SMS: Hello from Raspberry Pi!"
    print(f"\n[*] TEST 2: Sending SMS Push Notice (Opcode 0x6B, Icon=0): '{sms_text}'...")
    sms_payload = get_notice_payload(0, sms_text)
    sms_chunks = build_master_packet(0, 1, 0x6B, sms_payload)
    await send_command(sms_chunks, "SMS Notification Banner")
    
    print("\n[*] Commands sent! Holding connection open for 10 seconds...")
    for sec in range(10, 0, -1):
        print(f"    Closing in {sec}s... (Check watch screen now!)", end="\r")
        await asyncio.sleep(1.0)
        
    print("\n\n[+] Automated notification test complete! Disconnecting cleanly.")

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
