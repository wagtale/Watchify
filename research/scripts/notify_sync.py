#!/usr/bin/env python3
import asyncio
import struct
import sys
import time
import argparse
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
APP_MAP = {
    'call': 1,
    'sms': 2,
    'qq': 3,
    'wechat': 4,
    'email': 5,
    'facebook': 6,
    'twitter': 7,
    'whatsapp': 8,
    'instagram': 9,
    'skype': 10,
    'linkedin': 11,
    'line': 12,
    'other': 13
}

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
    """
    Constructs a notification payload conforming exactly to ProtocolAppToDevice.k()
    Format: 4 bytes timestamp + 1 byte app_id + 1 byte list size (2)
            + [1 byte title_attr, 1 byte title_len, title_bytes]
            + [1 byte body_attr (2), 1 byte body_len, body_bytes]
    """
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
    # Truncate body so total payload size fits within safe MTU fragment limits (max payload ~228 bytes)
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
    
    parser = argparse.ArgumentParser(description="Watch Notification Sync Tool")
    parser.add_argument('--mac', default=MAC_ADDRESS, help=f"Watch MAC (default: {MAC_ADDRESS})")
    parser.add_argument('--app', default='whatsapp', choices=APP_MAP.keys(), help="App name/icon to show")
    parser.add_argument('--title', type=str, help="Notification sender/title")
    parser.add_argument('--body', type=str, help="Notification message body")
    args = parser.parse_args()
    
    app_id = APP_MAP[args.app]
    title = args.title
    body = args.body
    
    # If no manual message is provided, create a couple of realistic dummies!
    dummies = []
    if title is None or body is None:
        print("[*] No custom notification provided. Pushing 2 dummy alerts...")
        dummies.append((APP_MAP['whatsapp'], "Boss", "Rebuilt weather app works perfectly! Excellent work!"))
        dummies.append((APP_MAP['sms'], "Mom", "Don't forget to eat dinner, dear!"))
    else:
        dummies.append((app_id, title, body))
        
    print(f"[*] Connecting to watch at {args.mac}...")
    async with BleakClient(args.mac, timeout=15.0) as client:
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

        # 2. Push Notification Alerts (Opcode 107 / 0x6B)
        for idx, (app, t, b) in enumerate(dummies):
            print(f"\n[>] Pushing Alert #{idx+1} ({args.app if args.title else list(APP_MAP.keys())[list(APP_MAP.values()).index(app)]}): '{t}: {b}'...")
            payload = build_notification_payload(app, t, b)
            chunks = build_master_packet(0, 1, 107, payload)
            await send_command(chunks, "Notification Update")
            if len(dummies) > 1 and idx < len(dummies) - 1:
                # Sleep a few seconds between alerts so they display sequentially on screen
                print("[*] Waiting 4 seconds before pushing next alert...")
                await asyncio.sleep(4.0)
        
        print("[+] Notification push completed successfully! Keeping connection alive for 2s...")
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
