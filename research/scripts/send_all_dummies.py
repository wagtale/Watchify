#!/usr/bin/env python3
import asyncio
import struct
import sys
import time
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0104007b0108007c01ff07000005007801000000"
    "00000000000000000000"
)

# App Package/Category ID mappings from NewsNotificationListenerService.java
APP_DETAILS = [
    (1, "Call Alert", "Incoming call from Boss"),
    (2, "SMS Message", "Mom: Don't forget to eat dinner!"),
    (3, "QQ", "Friend: Are you online?"),
    (4, "WeChat", "Alice: Sent you a red packet!"),
    (5, "Email", "Vanguard: Your monthly statement is ready."),
    (6, "Facebook", "Bob liked your status update."),
    (7, "Twitter/X", "Elon Musk posted a new tweet."),
    (8, "WhatsApp", "David: See you at the coffee shop!"),
    (9, "Instagram", "Sarah started a live video."),
    (10, "Skype", "Work Group: Meeting starting now."),
    (11, "LinkedIn", "Recruiter viewed your profile."),
    (12, "Line", "LINE Team: Welcome to the official channel!"),
    (13, "System Alert", "Battery fully charged (100%).")
]

client_ref = None
pid_counter = 0
time_sync_done = asyncio.Event()

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

def build_notification_payload(app_id: int, title: str, body: str) -> bytes:
    timestamp = int(time.time())
    bArr = bytearray(struct.pack("<I", timestamp))
    bArr.append(app_id & 0xFF)
    bArr.append(2)  # 2 notice elements: title and body
    
    # Item 1: Title
    title_bytes = title.encode('utf-8')[:64]
    title_attr = 1 if title.isdigit() else 0
    bArr.append(title_attr)
    bArr.append(len(title_bytes))
    bArr.extend(title_bytes)
    
    # Item 2: Body
    body_bytes = body.encode('utf-8')
    max_body_len = 220 - len(bArr)
    body_bytes = body_bytes[:max_body_len]
    bArr.append(2)  # body attribute is always 2
    bArr.append(len(body_bytes))
    bArr.extend(body_bytes)
    
    return bytes(bArr)

async def send_command(chunks: list[bytes], label: str):
    for idx, chunk in enumerate(chunks):
        await client_ref.write_gatt_char(WRITE_UUID, chunk, response=False)
        print(f"[>] Sent {label} (Chunk {idx+1}/{len(chunks)}): {chunk.hex()}")
        if len(chunks) > 1:
            await asyncio.sleep(0.05)

async def telemetry_handler(sender, data: bytearray):
    if len(data) >= 3 and data[0] == 0x00 and data[2] == 0x0C:
        print("[!] Sync Request received from Watch. Sending Time Sync...")
        await send_command(build_master_packet(0, 1, 0x0C, get_time_sync_payload()), "Time Sync")
        time_sync_done.set()
    elif len(data) >= 4 and data[0] == 0x00 and data[2] == 0x00:
        acked_opcode = data[3]
        print(f"[<] Watch acknowledged Opcode 0x{acked_opcode:02X}")
        if acked_opcode == 0x0C:
            time_sync_done.set()

async def main():
    global client_ref
    
    print(f"[*] Connecting to watch at {MAC_ADDRESS}...")
    async with BleakClient(MAC_ADDRESS, timeout=15.0) as client:
        client_ref = client
        if not client.is_connected:
            print("[-] Connection failed.")
            return
            
        print("[+] Connected! Starting notifications...")
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await asyncio.sleep(0.5)
        
        # 1. Send Binding Handshake
        print("[>] Sending binding handshake...")
        await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
        
        # Wait up to 3 seconds for Time Sync trigger from watch
        print("[*] Waiting for watch to request time sync...")
        try:
            await asyncio.wait_for(time_sync_done.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            print("[!] Timeout waiting for watch sync request. Sending manual Time Sync...")
            await send_command(build_master_packet(0, 1, 0x0C, get_time_sync_payload()), "Time Sync")
            
        await asyncio.sleep(0.5)

        # 2. Loop through all platforms one at a time
        for idx, (app_id, title, body) in enumerate(APP_DETAILS):
            print(f"\n[+] Pushing Platform {app_id}/13 - '{title}'...")
            payload = build_notification_payload(app_id, title, body)
            chunks = build_master_packet(0, 1, 107, payload)
            await send_command(chunks, f"Notice {title}")
            
            # Wait 4.5 seconds for watch to render and play vibration
            print("[*] Sleeping 4.5s to let you view it...")
            await asyncio.sleep(4.5)
            
        print("\n[+] All 13 platform dummy notifications pushed successfully! Keeping connection alive for 2s...")
        await asyncio.sleep(2.0)
        
        print("[*] Stopping notifications and disconnecting.")
        await client.stop_notify(NOTIFY_UUID)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[-] Fatal Error: {e}")
        sys.exit(1)
