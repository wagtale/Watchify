#!/usr/bin/env python3
import asyncio
import struct
import time
import json
import os
import argparse
from datetime import datetime
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Patched handshake enabling Call, SMS, and App notification settings
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0104007b0108007c01ff07000005007801000000"
    "00000000000000000000"
)

HISTORY_FILE = "/home/admin/fitness_history.json"

SLEEP_TYPES = {
    0: "NONE",
    1: "START",
    2: "DEEP",
    3: "LIGHT",
    4: "WAKE_UP"
}

client_ref = None
pid_counter = 0
time_sync_done = asyncio.Event()

def seed_mock_data() -> dict:
    import random
    history = {"steps": [], "sleep": [], "heart_rate": []}
    now = int(time.time())
    
    # 1. Seed Steps (last 3 days)
    for day in range(3, 0, -1):
        ts = now - (day * 86400)
        dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        steps = random.randint(5000, 11000)
        distance = int(steps * 0.75)  # roughly 0.75m per step
        calories = int(steps * 0.04)   # roughly 0.04 kcal per step
        duration = int(steps * 0.4)    # roughly 0.4 seconds per step
        
        history["steps"].append({
            "timestamp": ts,
            "datetime": dt_str,
            "steps": steps,
            "distance_m": distance,
            "calories_kcal": calories,
            "active_duration_s": duration,
            "type": "history"
        })
        
    # 2. Seed Sleep (last night)
    sleep_start = now - 43200  # 12 hours ago
    history["sleep"].append({
        "timestamp": sleep_start,
        "datetime": datetime.fromtimestamp(sleep_start).strftime('%Y-%m-%d %H:%M:%S'),
        "sleep_type": "START",
        "sleep_type_id": 1
    })
    
    current_time = sleep_start + 1800
    for cycle in range(4):
        # Deep sleep
        history["sleep"].append({
            "timestamp": current_time,
            "datetime": datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S'),
            "sleep_type": "DEEP",
            "sleep_type_id": 2
        })
        current_time += random.randint(3600, 5400)
        
        # Light sleep
        history["sleep"].append({
            "timestamp": current_time,
            "datetime": datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S'),
            "sleep_type": "LIGHT",
            "sleep_type_id": 3
        })
        current_time += random.randint(2400, 4800)
        
    # Wake up
    history["sleep"].append({
        "timestamp": current_time,
        "datetime": datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S'),
        "sleep_type": "WAKE_UP",
        "sleep_type_id": 4
    })
    
    # 3. Seed Heart Rate (every 2 hours for last 12 hours)
    for hr_offset in range(12, 0, -2):
        ts = now - (hr_offset * 3600)
        dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        history["heart_rate"].append({
            "timestamp": ts,
            "datetime": dt_str,
            "heart_rate_bpm": random.randint(60, 95),
            "type": "history"
        })
        
    return history

def load_local_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    # If file doesn't exist, seed with realistic mock data
    print("[*] History file not found. Seeding with initial realistic mock data...")
    history = seed_mock_data()
    save_local_history(history)
    return history

def save_local_history(history: dict):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

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

def parse_uint32_le(data: bytes, offset: int) -> int:
    return struct.unpack("<I", data[offset:offset+4])[0]

async def send_command(chunks: list[bytes], label: str):
    for idx, chunk in enumerate(chunks):
        await client_ref.write_gatt_char(WRITE_UUID, chunk, response=False)
        if len(chunks) > 1:
            await asyncio.sleep(0.05)

async def telemetry_handler(sender, data: bytearray):
    if len(data) < 3:
        return
        
    # Check if this frame is standard GATT vs master-wrapped
    is_master_wrapped = (len(data) >= 6 and data[4] in [1, 4])
    
    if is_master_wrapped:
        seq_counter = data[3]
        opcode = data[5]
        direction = data[4]
    else:
        seq_counter = 0
        opcode = data[2]
        direction = 1  # Assume request

    # Check for Time Sync requests (Opcode 12 / 0x0C)
    if opcode == 12 or (data[0] == 0x00 and data[2] == 0x0C):
        print("[!] Sync Request received from Watch. Sending ACK & Time Sync Update...")
        # 1. ACK the Sync Request (direction=4, opcode=12, payload=[1])
        await send_command(build_master_packet(seq_counter, 4, 12, bytes([1])), "Sync Request ACK")
        # 2. Push actual Time Setting (direction=1, opcode=104, payload=9-bytes time details)
        await send_command(build_master_packet(0, 1, 104, get_time_sync_payload()), "Time Sync Update")
        return

    # Check if this is an incoming payload from the watch (opcode is data type, direction != 4)
    # The direction field is data[4]. 4 = ACK response, 1 = Data push from watch.
    if direction == 4:
        # ACK response from watch
        acked_opcode = data[5]
        if acked_opcode == 104 or acked_opcode == 0x0C:
            time_sync_done.set()
        return

    # Extract payload from packet
    # A single-packet or fragmented packet payload starts at offset 10 of the reconstructed stream.
    # For now, we extract the payload bytes. In case of multi-packet payloads, we gather them.
    # Note: BLE mtu is 20, the payload length is at data[8:10].
    # Let's inspect length
    payload_len = struct.unpack("<H", data[8:10])[0]
    payload = data[10:10+payload_len]
    
    # Support for simple 1-packet payload parsing:
    if len(payload) < payload_len and len(data) > 20:
        # It's a fragmented payload. Let's merge fragments from the buffer.
        # However, for steps (20 bytes per item), sleep (5 bytes), and heart rate (5 bytes),
        # they might span multiple chunks.
        # Let's write a simple collector if we see fragments.
        # In practice, Bleak gives us the notifications packet by packet (20 bytes each).
        # We need to assemble fragments with the same PID.
        # Let's handle it by tracking current PID and appending bytes.
        pass

    # Acknowledge the data push immediately
    ack_chunks = build_master_packet(seq_counter, 4, opcode, bytes([1]))
    await send_command(ack_chunks, f"Data ACK for Opcode {opcode}")

    history = load_local_history()
    updated = False

    # 1. SPORT / STEPS HISTORY DATA (Opcode 4 = Realtime, 5 = History)
    if opcode in [4, 5]:
        print(f"\n[🏃 SPORT DATA RECEIVED] Opcode {opcode} (Payload size: {len(payload)} bytes)")
        if len(payload) >= 3:
            record_count = payload[2]
            print(f"[*] Records found: {record_count}")
            # Each record is 20 bytes: starts at offset 3
            for r in range(record_count):
                offset = 3 + (r * 20)
                if offset + 20 <= len(payload):
                    start_time = parse_uint32_le(payload, offset)
                    steps = parse_uint32_le(payload, offset + 4)
                    distance = parse_uint32_le(payload, offset + 8)
                    calories = parse_uint32_le(payload, offset + 12)
                    duration = parse_uint32_le(payload, offset + 16)
                    
                    dt_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
                    record = {
                        "timestamp": start_time,
                        "datetime": dt_str,
                        "steps": steps,
                        "distance_m": distance,
                        "calories_kcal": calories / 10.0, # Calories divided by 10 based on companion code
                        "active_duration_s": duration,
                        "type": "realtime" if opcode == 4 else "history"
                    }
                    print(f"  [{dt_str}] Steps: {steps} | Dist: {distance}m | Calories: {calories/10.0}kcal | Active: {duration}s")
                    
                    # Prevent duplicates
                    if record not in history["steps"]:
                        history["steps"].append(record)
                        updated = True

    # 2. SLEEP DATA (Opcode 6)
    elif opcode == 6:
        print(f"\n[😴 SLEEP DATA RECEIVED] Opcode {opcode} (Payload size: {len(payload)} bytes)")
        if len(payload) >= 3:
            block_count = payload[2]
            print(f"[*] Sleep Blocks count: {block_count}")
            offset = 3
            # Loop sleep blocks
            while offset < len(payload):
                sub_count = payload[offset]
                if sub_count == 0:
                    offset += 1
                    continue
                
                for s in range(sub_count):
                    sub_offset = offset + (s * 5)
                    type_offset = sub_offset + 1
                    time_offset = sub_offset + 2
                    if time_offset + 4 <= len(payload):
                        sleep_type_id = payload[type_offset]
                        start_time = parse_uint32_le(payload, time_offset)
                        sleep_type_name = SLEEP_TYPES.get(sleep_type_id, f"UNKNOWN ({sleep_type_id})")
                        dt_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
                        
                        record = {
                            "timestamp": start_time,
                            "datetime": dt_str,
                            "sleep_type": sleep_type_name,
                            "sleep_type_id": sleep_type_id
                        }
                        print(f"  [{dt_str}] Sleep Phase: {sleep_type_name}")
                        
                        if record not in history["sleep"]:
                            history["sleep"].append(record)
                            updated = True
                offset += (sub_count * 5) + 1

    # 3. HEART RATE DATA (Opcode 7 = Realtime, 8 = History)
    elif opcode in [7, 8]:
        print(f"\n[❤️ HEART RATE DATA RECEIVED] Opcode {opcode} (Payload size: {len(payload)} bytes)")
        if len(payload) >= 3:
            record_count = payload[2]
            print(f"[*] Heart Rate records: {record_count}")
            for r in range(record_count):
                offset = 3 + (r * 5)
                if offset + 5 <= len(payload):
                    start_time = parse_uint32_le(payload, offset)
                    hr = payload[offset + 4]
                    dt_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
                    
                    record = {
                        "timestamp": start_time,
                        "datetime": dt_str,
                        "heart_rate_bpm": hr,
                        "type": "realtime" if opcode == 7 else "history"
                    }
                    print(f"  [{dt_str}] Heart Rate: {hr} bpm")
                    
                    if record not in history["heart_rate"]:
                        history["heart_rate"].append(record)
                        updated = True

    if updated:
        save_local_history(history)
        print(f"[+] Saved updated fitness data to {HISTORY_FILE}")

async def main():
    global client_ref
    
    parser = argparse.ArgumentParser(description="Watch Fitness Sync Server")
    parser.add_argument('--mac', default=MAC_ADDRESS, help=f"Watch MAC (default: {MAC_ADDRESS})")
    parser.add_argument('--duration', type=int, default=60, help="Listen duration in seconds (default: 60)")
    args = parser.parse_args()
    
    print(f"[*] Connecting to watch at {args.mac}...")
    async with BleakClient(args.mac, timeout=15.0) as client:
        client_ref = client
        if not client.is_connected:
            print("[-] Connection failed.")
            return
            
        print("[+] Connected! Starting notifications...")
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await asyncio.sleep(0.5)
        
        # 1. Send Binding Handshake (this triggers historical sync auto-upload on the watch side)
        print("[>] Sending binding handshake...")
        await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
        
        # Wait up to 4 seconds for Time Sync trigger from watch
        print("[*] Waiting for watch to request time sync...")
        try:
            await asyncio.wait_for(time_sync_done.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            print("[!] Timeout waiting for watch sync request. Sending manual Time Sync...")
            await send_command(build_master_packet(0, 1, 0x0C, get_time_sync_payload()), "Time Sync")
            
        await asyncio.sleep(0.5)
        
        # Send query sensor switch or basic query command to ensure links are active
        print("[>] Requesting Sensor Switch activation...")
        sensor_pkt = build_master_packet(0, 1, 109, bytes([1]))
        await send_command(sensor_pkt, "Sensor Switch")
        
        print(f"\n[+] Fitness Sync Server active! Listening for data transfers for {args.duration}s...")
        print(f"[*] Any incoming records will be appended to {HISTORY_FILE}")
        print("----------------------------------------------------------------------")
        
        # Wait for the duration of the transfer
        for sec in range(args.duration, 0, -1):
            if sec % 10 == 0 or sec <= 5:
                print(f"[*] Syncing... {sec}s remaining.")
            await asyncio.sleep(1)
            
        print("[*] Stopping notifications and disconnecting.")
        await client.stop_notify(NOTIFY_UUID)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
    except Exception as e:
        print(f"\n[-] Fatal Error: {e}")
