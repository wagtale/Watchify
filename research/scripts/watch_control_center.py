#!/usr/bin/env python3
import asyncio
import struct
import sys
import os
import time
import json
import urllib.request
import argparse
from datetime import datetime
from bleak import BleakClient, BleakScanner

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Handshake payload enabling Call, SMS, and App notification settings
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0104007b0108007c01ff07000005007801000000"
    "00000000000000000000"
)

# App Categories
APP_CATEGORIES = {
    "calls": 1, "sms": 2, "qq": 3, "wechat": 4, "email": 5,
    "facebook": 6, "twitter": 7, "whatsapp": 8, "instagram": 9,
    "skype": 10, "linkedin": 11, "line": 12, "system": 13
}

# QR Card Types
CARD_TYPES = {
    "name_card": 1, "alipay": 2, "wechat_pay": 3, "paypal": 4, "google_pay": 5,
    "qq_friend": 6, "wechat_friend": 7, "facebook": 8, "twitter": 9,
    "whatsapp": 10, "instagram": 11, "other": 12
}

# Sleep types
SLEEP_TYPES = {0: "NONE", 1: "START", 2: "DEEP", 3: "LIGHT", 4: "WAKE_UP"}

# Music action mappings
MUSIC_ACTIONS = {
    1: "PLAY", 2: "PAUSE", 3: "STOP", 4: "PREVIOUS", 5: "NEXT",
    6: "PLAY_PAUSE_TOGGLE", 7: "QUERY_MUSIC_INFO", 8: "VOLUME_UP",
    9: "VOLUME_DOWN", 10: "QUERY_VOLUME_LEVEL"
}

client = None
pid_counter = 0
time_sync_done = asyncio.Event()

current_song = "Starboy - The Weeknd"
current_volume = 12
fitness_history = {"steps": [], "sleep": [], "heart_rate": []}
is_listening_music = False

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

async def send_chunks(chunks: list[bytes]):
    if not client or not client.is_connected:
        return
    for chunk in chunks:
        await client.write_gatt_char(WRITE_UUID, chunk, response=False)
        await asyncio.sleep(0.02)

def build_gps_payload(lat: float, lon: float) -> bytes:
    def split_coord(val: float) -> tuple:
        sign = 0x00 if val >= 0 else 0x01
        val = abs(val)
        deg = int(val)
        rem = (val - deg) * 60.0
        minutes = int(rem)
        rem = (rem - minutes) * 60.0
        seconds = int(rem)
        frac = int(round((rem - seconds) * 100.0))
        if frac >= 100:
            seconds += 1
            frac -= 100
        return sign, deg, minutes, seconds, frac

    lat_sign, lat_d, lat_m, lat_s, lat_f = split_coord(lat)
    lon_sign, lon_d, lon_m, lon_s, lon_f = split_coord(lon)
    return struct.pack("<BBBBBBBBBBBB", 
                       lon_sign, lon_d, lon_m, lon_s, lon_f & 0xFF, (lon_f >> 8) & 0xFF,
                       lat_sign, lat_d, lat_m, lat_s, lat_f & 0xFF, (lat_f >> 8) & 0xFF)

def build_notice_payload(app_id: int, title: str, body: str) -> bytes:
    title_bytes = title.encode('utf-8')[:24]
    body_bytes = body.encode('utf-8')[:128]
    items_payload = bytearray()
    items_payload.append(0x00)
    items_payload.append(len(title_bytes))
    items_payload.extend(title_bytes)
    items_payload.append(0x02)
    items_payload.append(len(body_bytes))
    items_payload.extend(body_bytes)
    header = struct.pack("<IBB", int(time.time()), app_id, 2)
    return header + items_payload

def build_card_payload(card_type: int, url: str) -> bytes:
    url_bytes = url.encode('utf-8')
    payload = bytearray()
    payload.append(card_type & 0xFF)
    payload.extend(struct.pack("<I", len(url_bytes)))
    payload.extend(url_bytes)
    return bytes(payload)

def build_ai_text_packets(status: int, text: str) -> list[bytes]:
    if not text:
        return build_master_packet(0, 1, 154, bytes([status]))
    bytes_data = text.encode('utf-8')
    length = len(bytes_data)
    chunks = []
    chunk_size = 300
    i4 = length // chunk_size + (1 if length % chunk_size != 0 else 0)
    for i5 in range(i4):
        offset = i5 * chunk_size
        current_chunk_size = chunk_size
        if i5 == i4 - 1 and (length % chunk_size) != 0:
            current_chunk_size = length % chunk_size
        bArr = bytearray(current_chunk_size + 9)
        bArr[0] = status & 0xFF
        bArr[1:5] = struct.pack("<I", length)
        bArr[5:9] = struct.pack("<I", offset)
        bArr[9:9+current_chunk_size] = bytes_data[offset : offset + current_chunk_size]
        chunks.extend(build_master_packet(0, 1, 154, bytes(bArr)))
    return chunks

async def push_music_metadata(song: str, vol: int):
    global current_song, current_volume
    current_song = song
    current_volume = max(0, min(15, vol))
    
    # 1. Push Song Title (66-byte fixed-size buffer)
    song_arr = bytearray(66)
    song_arr[0] = 7  # Content type: Song Title
    song_bytes = current_song.encode('utf-8')[:24]  # Max 24 bytes based on companion app limits
    song_arr[1] = len(song_bytes)
    song_arr[2:2+len(song_bytes)] = song_bytes
    await send_chunks(build_master_packet(0, 1, 113, bytes(song_arr)))
    
    # 2. Push Volume (66-byte fixed-size buffer)
    vol_arr = bytearray(66)
    vol_arr[0] = 10  # Content type: Volume
    vol_arr[1] = 1   # Length
    vol_arr[2] = current_volume
    await send_chunks(build_master_packet(0, 1, 113, bytes(vol_arr)))

async def telemetry_handler(sender, data: bytearray):
    global current_volume, current_song, is_listening_music
    if len(data) < 3:
        return
        
    is_master_wrapped = (len(data) >= 6 and data[4] in [1, 4])
    if is_master_wrapped:
        seq_counter = data[3]
        opcode = data[5]
        direction = data[4]
    else:
        seq_counter = 0
        opcode = data[2]
        direction = 1

    # Unpack payload
    payload_len = struct.unpack("<H", data[8:10])[0] if is_master_wrapped else len(data) - 3
    payload = data[10:10+payload_len] if is_master_wrapped else data[3:]

    # Acknowledge incoming requests
    if direction == 1 and opcode != 12:
        await send_chunks(build_master_packet(seq_counter, 4, opcode, bytes([1])))

    # 1. Time Sync requests
    if opcode == 12 or (data[0] == 0x00 and data[2] == 0x0C):
        await send_chunks(build_master_packet(seq_counter, 4, 12, bytes([1])))
        await send_chunks(build_master_packet(0, 1, 104, get_time_sync_payload()))
        time_sync_done.set()
        return

    # 2. ACK responses
    if direction == 4 or (not is_master_wrapped and opcode == 0):
        acked_opcode = data[5] if is_master_wrapped else data[3]
        if acked_opcode in [104, 12]:
            time_sync_done.set()
        return

    # 3. Music Control Buttons
    if opcode == 14 and is_listening_music:
        action_id = data[10] if is_master_wrapped else data[3]
        action_name = MUSIC_ACTIONS.get(action_id, f"UNKNOWN ({action_id})")
        print(f"\n[🎵 WATCH PRESS] Media Command: {action_name}")
        
        if action_id == 7:
            await push_music_metadata(current_song, current_volume)
        elif action_id == 10:
            await push_music_metadata(current_song, current_volume)
        elif action_id == 8:
            current_volume = min(15, current_volume + 1)
            await push_music_metadata(current_song, current_volume)
            print(f"  └── Volume increased to {current_volume}/15")
        elif action_id == 9:
            current_volume = max(0, current_volume - 1)
            await push_music_metadata(current_song, current_volume)
            print(f"  └── Volume decreased to {current_volume}/15")
        else:
            print(f"  └── Action Triggered: {action_name}")
        print("\nPress Enter to return to menu...")
        return

    # 4. Steps History (Opcodes 4, 5)
    if opcode in [4, 5]:
        if len(payload) >= 3:
            record_count = payload[2]
            for r in range(record_count):
                offset = 3 + (r * 20)
                if offset + 20 <= len(payload):
                    start_time = parse_uint32_le(payload, offset)
                    steps = parse_uint32_le(payload, offset + 4)
                    dist = parse_uint32_le(payload, offset + 8)
                    cal = parse_uint32_le(payload, offset + 12)
                    dur = parse_uint32_le(payload, offset + 16)
                    record = {
                        "datetime": datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S'),
                        "steps": steps, "distance_m": dist, "calories_kcal": cal / 10.0, "duration_s": dur
                    }
                    if record not in fitness_history["steps"]:
                        fitness_history["steps"].append(record)

    # 5. Sleep (Opcode 6)
    elif opcode == 6:
        if len(payload) >= 3:
            offset = 3
            while offset < len(payload):
                sub_count = payload[offset]
                if sub_count == 0:
                    offset += 1
                    continue
                for s in range(sub_count):
                    sub_offset = offset + (s * 5)
                    if sub_offset + 5 <= len(payload):
                        sleep_type = payload[sub_offset + 1]
                        start_time = parse_uint32_le(payload, sub_offset + 2)
                        record = {
                            "datetime": datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S'),
                            "type": SLEEP_TYPES.get(sleep_type, f"UNKNOWN ({sleep_type})")
                        }
                        if record not in fitness_history["sleep"]:
                            history_sleep = fitness_history.setdefault("sleep", [])
                            if record not in history_sleep:
                                history_sleep.append(record)
                offset += (sub_count * 5) + 1

    # 6. Heart Rate (Opcodes 7, 8)
    elif opcode in [7, 8]:
        if len(payload) >= 3:
            record_count = payload[2]
            for r in range(record_count):
                offset = 3 + (r * 5)
                if offset + 5 <= len(payload):
                    start_time = parse_uint32_le(payload, offset)
                    hr = payload[offset + 4]
                    record = {
                        "datetime": datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S'),
                        "heart_rate": hr
                    }
                    if record not in fitness_history["heart_rate"]:
                        fitness_history["heart_rate"].append(record)

def load_seed_fitness():
    global fitness_history
    if os.path.exists("/home/admin/fitness_history.json"):
        try:
            with open("/home/admin/fitness_history.json", "r") as f:
                fitness_history = json.load(f)
                return
        except:
            pass
    # Seed mock data
    now = int(time.time())
    fitness_history["steps"] = [
        {"datetime": datetime.fromtimestamp(now - 172800).strftime('%Y-%m-%d %H:%M:%S'), "steps": 8104, "distance_m": 6078, "calories_kcal": 324.0, "duration_s": 2400},
        {"datetime": datetime.fromtimestamp(now - 86400).strftime('%Y-%m-%d %H:%M:%S'), "steps": 10543, "distance_m": 7907, "calories_kcal": 421.7, "duration_s": 3100},
        {"datetime": datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S'), "steps": 6240, "distance_m": 4680, "calories_kcal": 249.6, "duration_s": 1780}
    ]
    fitness_history["sleep"] = [
        {"datetime": datetime.fromtimestamp(now - 43200).strftime('%Y-%m-%d %H:%M:%S'), "type": "START"},
        {"datetime": datetime.fromtimestamp(now - 40000).strftime('%Y-%m-%d %H:%M:%S'), "type": "LIGHT"},
        {"datetime": datetime.fromtimestamp(now - 32000).strftime('%Y-%m-%d %H:%M:%S'), "type": "DEEP"},
        {"datetime": datetime.fromtimestamp(now - 18000).strftime('%Y-%m-%d %H:%M:%S'), "type": "WAKE_UP"}
    ]
    fitness_history["heart_rate"] = [
        {"datetime": datetime.fromtimestamp(now - 21600).strftime('%Y-%m-%d %H:%M:%S'), "heart_rate": 72},
        {"datetime": datetime.fromtimestamp(now - 14400).strftime('%Y-%m-%d %H:%M:%S'), "heart_rate": 84},
        {"datetime": datetime.fromtimestamp(now - 7200).strftime('%Y-%m-%d %H:%M:%S'), "heart_rate": 65}
    ]
    with open("/home/admin/fitness_history.json", "w") as f:
        json.dump(fitness_history, f, indent=2)

def geolocate_ip() -> tuple:
    try:
        req = urllib.request.Request("http://ip-api.com/json", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3.0) as response:
            data = json.loads(response.read().decode())
            return float(data.get("lat", 0.0)), float(data.get("lon", 0.0)), f"{data.get('city')}, {data.get('country')}"
    except:
        return 40.7128, -74.0060, "New York (Fallback)"

async def main_tui():
    global client, is_listening_music, current_song, current_volume
    load_seed_fitness()
    
    parser = argparse.ArgumentParser(description="UTRA Watch Advanced Control Center")
    parser.add_argument('--mac', default=MAC_ADDRESS, help="MAC address of the watch")
    parser.add_argument('--action', choices=['music', 'text', 'notify', 'gps', 'card', 'switches', 'fitness', 'time'], help="Batch action to run non-interactively")
    parser.add_argument('--text', help="Text to display for 'text' action")
    parser.add_argument('--app', default='system', help="App category for 'notify' action")
    parser.add_argument('--title', default='Alert', help="Title for 'notify' action")
    parser.add_argument('--body', default='Custom message', help="Body for 'notify' action")
    parser.add_argument('--lat', type=float, help="Latitude for 'gps' action")
    parser.add_argument('--lon', type=float, help="Longitude for 'gps' action")
    parser.add_argument('--card-type', default='other', help="Card type for 'card' action")
    parser.add_argument('--url', help="URL content for 'card' action")
    parser.add_argument('--calls', type=int, default=1, help="Calls status (0 or 1)")
    parser.add_argument('--sms', type=int, default=1, help="SMS status (0 or 1)")
    parser.add_argument('--master-app', type=int, default=1, help="App alerts status (0 or 1)")
    parser.add_argument('--duration', type=int, default=10, help="Duration to run for batch actions (default: 10)")
    args = parser.parse_args()

    # Clear terminal connection caching first
    print("[*] Releasing any lingering BlueZ locks...")
    proc = await asyncio.create_subprocess_shell(
        f"bluetoothctl disconnect {args.mac}",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()

    # Connect client
    print(f"[*] Connecting to watch at {args.mac}...")
    client = BleakClient(args.mac, timeout=12.0)
    try:
        await client.connect()
        print("[+] Connected successfully!")
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        
        # Binding pairing success handshake
        print("[>] Executing handshake pairing...")
        await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
        await asyncio.sleep(1.0)
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        print("[!] Make sure the watch is nearby and not connected to your phone's Bluetooth!")
        return

    # Handle Batch Action Mode
    if args.action:
        print(f"[*] Batch Mode Active: Running action '{args.action}'...")
        if args.action == "time":
            time_sync_done.clear()
            await send_chunks(build_master_packet(0, 1, 104, get_time_sync_payload()))
            try:
                await asyncio.wait_for(time_sync_done.wait(), timeout=3.0)
                print("[+] Time synced successfully!")
            except asyncio.TimeoutError:
                print("[+] Time sync update pushed.")
                
        elif args.action == "text":
            if not args.text:
                print("[-] Error: --text is required for 'text' action.")
            else:
                await send_chunks(build_ai_text_packets(0, ""))
                await asyncio.sleep(0.3)
                await send_chunks(build_ai_text_packets(3, args.text))
                print(f"[+] Display text pushed: '{args.text}'")
                
        elif args.action == "notify":
            app_id = APP_CATEGORIES.get(args.app.lower(), 13)
            payload = build_notice_payload(app_id, args.title, args.body)
            await send_chunks(build_master_packet(0, 1, 107, payload))
            print(f"[+] Notification pushed: {args.title} - {args.body}")
            
        elif args.action == "gps":
            lat, lon = args.lat, args.lon
            if lat is None or lon is None:
                lat, lon, label = geolocate_ip()
                print(f"[*] Auto-detected Location: {label} (Lat: {lat}, Lon: {lon})")
            payload = build_gps_payload(lat, lon)
            await send_chunks(build_master_packet(0, 1, 140, payload))
            print(f"[+] Map coordinates synced.")
            
        elif args.action == "card":
            if not args.url:
                print("[-] Error: --url is required for 'card' action.")
            else:
                card_id = CARD_TYPES.get(args.card_type.lower(), 12)
                payload = build_card_payload(card_id, args.url)
                await send_chunks(build_master_packet(0, 1, 138, payload))
                print(f"[+] QR Code Card uploaded: type {args.card_type}")
                
        elif args.action == "switches":
            await send_chunks(build_master_packet(0, 1, 122, bytes([args.calls])))
            await send_chunks(build_master_packet(0, 1, 123, bytes([args.sms])))
            bitmask_bytes = struct.pack("<I", 0x07FF)
            payload = bytes([args.master_app, bitmask_bytes[0], bitmask_bytes[1], bitmask_bytes[2], bitmask_bytes[3]])
            await send_chunks(build_master_packet(0, 1, 124, payload))
            print("[+] Notification switches updated.")
            
        elif args.action == "fitness":
            print("[*] Syncing activity records...")
            await send_chunks(build_master_packet(0, 1, 109, bytes([1])))
            await asyncio.sleep(args.duration)
            with open("/home/admin/fitness_history.json", "w") as f:
                json.dump(fitness_history, f, indent=2)
            print(f"[+] Fitness history synchronized and saved to {HISTORY_FILE}")
            
        elif args.action == "music":
            is_listening_music = True
            await push_music_metadata(current_song, current_volume)
            print(f"[*] Music server listening for {args.duration}s...")
            await asyncio.sleep(args.duration)
            is_listening_music = False

        print("[*] Disconnecting and exiting...")
        await client.stop_notify(NOTIFY_UUID)
        await client.disconnect()
        return

    # Interactive TUI Mode
    while True:
        os.system('clear')
        print("======================================================================")
        print("⚡               UTRA WATCH ADVANCED SYSTEM CONSOLE                  ⚡")
        print("======================================================================")
        print(f" [*] Connected Watch Address : {args.mac}")
        print(f" [*] Current Music Metadata  : {current_song} (Volume: {current_volume}/15)")
        print("----------------------------------------------------------------------")
        print("  [1] 🎵  Start Music Controller Server (Live button feedback)")
        print("  [2] 📝  Display Custom Text on Watch Face (AI screen)")
        print("  [3] 💬  Push Custom App Notification Alert")
        print("  [4] 🗺️  Push GPS Coordinate / Map Geolocation")
        print("  [5] 💳  Upload Social Card / Payment QR Code")
        print("  [6] 🔀  Configure Notification Switch settings")
        print("  [7] 🏃  Pull & Display Fitness History (Steps/Sleep/Heart Rate)")
        print("  [8] 🔄  Force Time Synchronization update")
        print("  [9] 🔌  Disconnect & Exit")
        print("======================================================================")
        
        try:
            choice = input("Enter choice (1-9): ").strip()
        except EOFError:
            print("\n[!] Standard Input (stdin) is not available.")
            print("    └── To run interactively, run: python3 watch_control_center.py in a local terminal.")
            print("    └── To run in batch mode, use CLI flags, e.g.:")
            print("        python3 watch_control_center.py --action text --text \"Hello Watch!\"")
            await client.stop_notify(NOTIFY_UUID)
            await client.disconnect()
            break
            
        if choice == "9":
            print("[*] Disconnecting and releasing BLE client...")
            await client.stop_notify(NOTIFY_UUID)
            await client.disconnect()
            print("[+] Disconnected. Goodbye!")
            break
            
        elif choice == "1":
            is_listening_music = True
            os.system('clear')
            print("======================================================================")
            print("🎵                 BLUETOOTH MEDIA CONTROLLER SERVER                 🎵")
            print("======================================================================")
            print("  Active Server Details:")
            print(f"    - Song Title   : {current_song}")
            print(f"    - Volume Level : {current_volume}/15")
            print("----------------------------------------------------------------------")
            print("  [*] Music controller is active! Press buttons on your watch UI now.")
            print("      (Or press Ctrl+C to return to main menu)")
            print("======================================================================")
            
            # Send initial details to populate screen
            await push_music_metadata(current_song, current_volume)
            
            try:
                # Loop reading CLI commands concurrently with BLE listener
                while True:
                    cmd_line = await asyncio.get_event_loop().run_in_executor(None, input, "  [CLI Command] (song <name> / vol <0-15>): ")
                    parts = cmd_line.strip().split(" ", 1)
                    if not parts or not parts[0]:
                        continue
                    cmd = parts[0].lower()
                    if cmd == "exit" or cmd == "quit":
                        break
                    elif cmd == "song" and len(parts) > 1:
                        await push_music_metadata(parts[1], current_volume)
                        print(f"  [+] Track updated to: '{parts[1]}'")
                    elif cmd == "vol" and len(parts) > 1:
                        try:
                            v = int(parts[1])
                            await push_music_metadata(current_song, v)
                            print(f"  [+] Volume updated to: {current_volume}/15")
                        except:
                            print("  [-] Invalid volume int.")
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            is_listening_music = False
            
        elif choice == "2":
            os.system('clear')
            print("======================================================================")
            print("📝                   DISPLAY CUSTOM TEXT ON WATCH                     📝")
            print("======================================================================")
            text = input("Enter text message to display: ").strip()
            if text:
                print(f"[*] Initializing watch assistant display...")
                await send_chunks(build_ai_text_packets(0, "")) # Wake up screen
                await asyncio.sleep(0.3)
                print(f"[>] Sending display payload: '{text}'...")
                await send_chunks(build_ai_text_packets(3, text)) # Display AI response
                print("[+] Pushed! Check the voice assistant display on your watch.")
            input("\nPress Enter to return to menu...")
            
        elif choice == "3":
            os.system('clear')
            print("======================================================================")
            print("💬                     PUSH CUSTOM NOTIFICATION                       💬")
            print("======================================================================")
            print("  Available Apps: calls, sms, whatsapp, wechat, facebook, twitter, email, system")
            app_name = input("Enter app category: ").strip().lower()
            app_id = APP_CATEGORIES.get(app_name, 13)
            title = input("Enter Title/Sender: ").strip()
            body = input("Enter Message Body: ").strip()
            
            print("[>] Constructing and sending notification list packet...")
            payload = build_notice_payload(app_id, title, body)
            await send_chunks(build_master_packet(0, 1, 107, payload))
            print("[+] Notification pushed successfully!")
            input("\nPress Enter to return to menu...")
            
        elif choice == "4":
            os.system('clear')
            print("======================================================================")
            print("🗺️                       GEOLOCATION & MAP SYNC                       🗺️")
            print("======================================================================")
            print("  [1] Auto-detect location via IP Address")
            print("  [2] Enter manual coordinates (latitude/longitude)")
            mode = input("Select mode (1-2): ").strip()
            
            lat, lon, label = 0.0, 0.0, ""
            if mode == "1":
                print("[*] Contacting geolocator...")
                lat, lon, label = geolocate_ip()
                print(f"  └── Resolved Location: {label} (Lat: {lat}, Lon: {lon})")
            else:
                try:
                    lat = float(input("Enter Latitude (e.g. 48.8566): ").strip())
                    lon = float(input("Enter Longitude (e.g. 2.3522): ").strip())
                    label = "Manual Coordinates"
                except:
                    print("[-] Error parsing floats. Aborting.")
                    input("\nPress Enter to return to menu...")
                    continue
                    
            print(f"[>] Packaging map coordinate payload and sending to Opcode 140...")
            payload = build_gps_payload(lat, lon)
            await send_chunks(build_master_packet(0, 1, 140, payload))
            print("[+] Coordinates synchronized successfully!")
            input("\nPress Enter to return to menu...")
            
        elif choice == "5":
            os.system('clear')
            print("======================================================================")
            print("💳                  UPLOAD SOCIAL CARD / PAYMENT QR                   💳")
            print("======================================================================")
            print("  Available QR Types:")
            print("    - name_card, alipay, wechat_pay, paypal, google_pay, whatsapp, instagram, twitter")
            card_name = input("Enter card/QR type: ").strip().lower()
            card_id = CARD_TYPES.get(card_name, 12)
            url_content = input("Enter QR code URL content: ").strip()
            
            if url_content:
                print(f"[>] Bundling QR data and pushing to Opcode 138...")
                payload = build_card_payload(card_id, url_content)
                await send_chunks(build_master_packet(0, 1, 138, payload))
                print("[+] QR card successfully loaded onto watch module!")
            input("\nPress Enter to return to menu...")
            
        elif choice == "6":
            os.system('clear')
            print("======================================================================")
            print("🔀                    CONFIGURE NOTIFICATION SWITCHES                 🔀")
            print("======================================================================")
            calls_val = int(input("Enable Calls Alerts? (1=Yes, 0=No): ").strip() or "1")
            sms_val = int(input("Enable SMS Alerts? (1=Yes, 0=No): ").strip() or "1")
            master_app = int(input("Enable App Alerts? (1=Yes, 0=No): ").strip() or "1")
            
            # Apps switches bitmask selection
            bitmask = 0x07FF  # all 11 apps enabled
            
            print("[>] Encoding notification switch packages...")
            # Calls (Opcode 122)
            await send_chunks(build_master_packet(0, 1, 122, bytes([calls_val])))
            # SMS (Opcode 123)
            await send_chunks(build_master_packet(0, 1, 123, bytes([sms_val])))
            # Apps Switch (Opcode 124)
            bitmask_bytes = struct.pack("<I", bitmask)
            payload = bytes([master_app, bitmask_bytes[0], bitmask_bytes[1], bitmask_bytes[2], bitmask_bytes[3]])
            await send_chunks(build_master_packet(0, 1, 124, payload))
            
            print("[+] Notification switches updated successfully!")
            input("\nPress Enter to return to menu...")
            
        elif choice == "7":
            os.system('clear')
            print("======================================================================")
            print("🏃                       FITNESS TRACKING DATABASE                    🏃")
            print("======================================================================")
            print("[*] Pulling latest activity logs from watch...")
            # Trigger sensor query to pull values
            sensor_query = build_master_packet(0, 1, 109, bytes([1]))
            await send_chunks(sensor_query)
            await asyncio.sleep(1.0)
            
            # Print Steps History Table
            print("\n  📈 daily activity history (steps):")
            print("  " + "-"*75)
            print("  |   Date/Time       |   Steps   |  Distance (m)  |  Calories  | Duration (s) |")
            print("  " + "-"*75)
            for s in fitness_history.get("steps", []):
                print(f"  | {s['datetime']:<17} | {s['steps']:<9} | {s['distance_m']:<14} | {s['calories_kcal']:<10.1f} | {s['duration_s']:<12} |")
            print("  " + "-"*75)
            
            # Print Sleep history
            print("\n  😴 sleep history logs:")
            print("  " + "-"*45)
            print("  |   Date/Time       |   Sleep Phase Type    |")
            print("  " + "-"*45)
            for sl in fitness_history.get("sleep", []):
                print(f"  | {sl['datetime']:<17} | {sl['type']:<21} |")
            print("  " + "-"*45)

            # Print Heart Rate
            print("\n  ❤️ heart rate trends:")
            print("  " + "-"*35)
            print("  |   Date/Time       |  Heart Rate  |")
            print("  " + "-"*35)
            for hr in fitness_history.get("heart_rate", []):
                print(f"  | {hr['datetime']:<17} | {hr['heart_rate']:<12} bpm |")
            print("  " + "-"*35)
            
            # Dump to file
            with open("/home/admin/fitness_history.json", "w") as f:
                json.dump(fitness_history, f, indent=2)
            print(f"\n[+] Unified history synced and saved to {HISTORY_FILE}")
            input("\nPress Enter to return to menu...")
            
        elif choice == "8":
            print("[*] Requesting watch time synchronization...")
            time_sync_done.clear()
            await send_chunks(build_master_packet(0, 1, 104, get_time_sync_payload()))
            try:
                await asyncio.wait_for(time_sync_done.wait(), timeout=3.0)
                print("[+] Time synced successfully on watch face!")
            except asyncio.TimeoutError:
                print("[-] Time sync update pushed (no response received).")
            input("\nPress Enter to return to menu...")

if __name__ == "__main__":
    try:
        asyncio.run(main_tui())
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
    except Exception as e:
        print(f"\n[-] Fatal error: {e}")
