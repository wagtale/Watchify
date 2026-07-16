#!/usr/bin/env python3
import asyncio
import struct
import sys
import time
import argparse
import requests
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0104007b0108007c01ff07000005007801000000"
    "00000000000000000000"
)

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

def encode_coordinate(val: float) -> bytes:
    """
    Encodes float coordinate to 6-byte degrees/minutes/seconds/fractional seconds.
    Matches logic in DeviceFragment.java.
    """
    bArr = bytearray(6)
    if val >= 0.0:
        bArr[0] = 43  # '+'
    else:
        bArr[0] = 45  # '-'
    
    abs_val = abs(val)
    bArr[1] = int(abs_val) & 0xFF
    
    d = (abs_val % 1.0) * 60.0
    bArr[2] = int(d) & 0xFF
    
    d2 = (d % 1.0) * 60.0
    bArr[3] = int(d2) & 0xFF
    
    d3 = d2 * 100.0
    bArr[4] = int(d3) & 0xFF
    bArr[5] = int((d3 % 1.0) * 100.0) & 0xFF
    
    return bytes(bArr)

def build_gps_payload(lat: float, lon: float) -> bytes:
    """Encodes lat and lon into the 12-byte payload expected by Opcode 140."""
    # First 6 bytes are Longitude (dB), next 6 bytes are Latitude (dA)
    lon_bytes = encode_coordinate(lon)
    lat_bytes = encode_coordinate(lat)
    return lon_bytes + lat_bytes

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

def get_public_ip_location() -> tuple:
    """Geolocates the machine using external public IP address lookup."""
    try:
        # Fetch public IP
        ip_resp = requests.get("https://api.ipify.org?format=json", timeout=5).json()
        ip = ip_resp.get("ip")
        if not ip:
            return None, None, "Unknown"
        
        # Geolocate coordinates
        geo_resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=5).json()
        if geo_resp.get("status") == "success":
            lat = geo_resp.get("lat")
            lon = geo_resp.get("lon")
            city = geo_resp.get("city")
            return lat, lon, f"{city} ({ip})"
    except Exception as e:
        print(f"[-] Geolocation error: {e}")
    return None, None, "Unknown"

async def main():
    global client_ref
    
    parser = argparse.ArgumentParser(description="Watch GPS Sync Tool")
    parser.add_argument('--mac', default=MAC_ADDRESS, help=f"Watch MAC (default: {MAC_ADDRESS})")
    parser.add_argument('--lat', type=float, help="Manual Latitude")
    parser.add_argument('--lon', type=float, help="Manual Longitude")
    args = parser.parse_args()
    
    lat, lon, loc_source = args.lat, args.lon, "Manual Input"
    if lat is None or lon is None:
        print("[*] Pulling current coordinates from public IP...")
        lat, lon, loc_source = get_public_ip_location()
        if lat is None or lon is None:
            # Default fallback (Cape Town)
            lat, lon, loc_source = -33.9249, 18.4241, "Cape Town (Fallback)"
            
    print(f"[+] Syncing coordinates to Map App: Lat={lat:.6f}, Lon={lon:.6f} [Source: {loc_source}]")
    gps_payload = build_gps_payload(lat, lon)
    
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

        # 2. Padded GPS Coordinate sync (Opcode 140 / 0x8C)
        print("[>] Pushing GPS Coordinates (0x8C)...")
        gps_chunks = build_master_packet(0, 1, 140, gps_payload)
        await send_command(gps_chunks, "GPS Location Update")
        
        print("[+] GPS sync completed successfully! Keeping connection alive for 2s...")
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
