#!/usr/bin/env python3
import asyncio
import struct
import sys
import time
import argparse
import requests
import os
from bleak import BleakClient, BleakError

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

# Weather condition to code mapping matching WTWD/UTRA watch firmware
WEATHER_MAP = {
    'sunny': 10,
    'clear': 10,
    'cloudy': 11,
    'few-clouds': 12,
    'partly-cloudy': 12,
    'overcast': 13,
    'windy': 14,
    'gale': 14,
    'snow-shower': 15,
    'warm': 15,
    'snow': 16,
    'snowy': 16,
    'rain': 17,
    'rainy': 17,
    'shower': 17,
    'storm': 18,
    'stormy': 18,
    'thunderstorm': 19,
    'hail': 20,
    'sleet': 21,
    'fog': 22,
    'foggy': 22,
    'haze': 22,
    'sandstorm': 23
}

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
    # 4 bytes current unix time, 4 bytes timezone offset (7200 for UTC+2), 1 byte DST/control
    return struct.pack("<IIB", int(time.time()), 7200, 0x01)

def build_weather_payload_3day(weather_list: list) -> bytes:
    """
    Constructs a 19-byte weather payload matching ProtocolAppToDevice.n()
    Format: 4 bytes timestamp + 3 weather records of 5 bytes each.
    Each record: 1 byte type, 1 byte low temp, 1 byte high temp, 2 bytes padding.
    """
    timestamp = int(time.time())
    payload = bytearray(struct.pack("<I", timestamp))
    
    for i in range(3):
        if i < len(weather_list):
            w_type, low, high = weather_list[i]
        else:
            w_type, low, high = 10, 15, 25  # default to sunny, 15-25C
        
        # Pack record: type, low, high
        payload.extend(struct.pack("<BBB", w_type & 0xFF, low & 0xFF, high & 0xFF))
        payload.extend(b"\x00\x00")  # 2 bytes padding for each entry
        
    return bytes(payload)

async def send_command(chunks: list[bytes], label: str):
    for idx, chunk in enumerate(chunks):
        await client_ref.write_gatt_char(WRITE_UUID, chunk, response=False)
        print(f"[>] Sent {label} (Chunk {idx+1}/{len(chunks)}): {chunk.hex()}")
        if len(chunks) > 1:
            await asyncio.sleep(0.05)

async def telemetry_handler(sender, data: bytearray):
    # Check for Time Sync Request (Opcode 0x0C)
    if len(data) >= 3 and data[0] == 0x00 and data[2] == 0x0C:
        print("[!] Sync Request received from Watch. Sending Time Sync...")
        await send_command(build_master_packet(0, 1, 0x0C, get_time_sync_payload()), "Time Sync")
        time_sync_done.set()
    elif len(data) >= 4 and data[0] == 0x00 and data[2] == 0x00:
        # Check for ACK of sent commands
        acked_opcode = data[3]
        print(f"[<] Watch acknowledged Opcode 0x{acked_opcode:02X}")
        if acked_opcode == 0x0C:
            time_sync_done.set()

def map_wmo_to_watch_type(wmo_code: int) -> int:
    """Maps WMO Weather Interpretation Codes (Open-Meteo) to watch weather types."""
    if wmo_code == 0:
        return 10  # Sunny / Clear
    elif wmo_code in [1, 2]:
        return 12  # Partly cloudy / Few clouds
    elif wmo_code == 3:
        return 13  # Overcast
    elif wmo_code in [45, 48]:
        return 22  # Fog / Haze
    elif wmo_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
        return 17  # Rain / Shower
    elif wmo_code in [56, 57, 66, 67]:
        return 21  # Sleet
    elif wmo_code in [71, 73, 75, 77]:
        return 16  # Snow / Snowy
    elif wmo_code in [85, 86]:
        return 15  # Snow shower
    elif wmo_code in [95]:
        return 19  # Thunderstorm
    elif wmo_code in [96, 99]:
        return 20  # Hail
    else:
        return 100  # Unknown

def map_accuweather_icon_to_watch_type(icon_id: int) -> int:
    """Maps AccuWeather Icon IDs (1-44) to watch weather types."""
    if icon_id in [1, 2, 30, 31, 33, 34]:
        return 10  # Sunny / Clear
    elif icon_id in [6, 38]:
        return 11  # Cloudy
    elif icon_id in [3, 4, 35, 36]:
        return 12  # Partly cloudy
    elif icon_id in [7, 8]:
        return 13  # Overcast
    elif icon_id in [32]:
        return 14  # Windy
    elif icon_id in [19, 20, 21, 22, 23, 43, 44]:
        return 16  # Snow / Snowy
    elif icon_id in [12, 13, 14, 18, 39, 40]:
        return 17  # Rain / Shower
    elif icon_id in [15, 16, 17, 41, 42]:
        return 19  # Thunderstorm
    elif icon_id in [24]:
        return 20  # Hail
    elif icon_id in [25, 26, 29]:
        return 21  # Sleet
    elif icon_id in [5, 11, 37]:
        return 22  # Fog / Haze
    else:
        return 100  # Unknown / Default

def get_public_ip() -> str:
    """Retrieves the public IP address of the machine using reliable ipify or ipinfo services."""
    for service in ["https://api.ipify.org?format=json", "https://ipinfo.io/json", "http://ip-api.com/json"]:
        try:
            resp = requests.get(service, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                ip = data.get("ip") or data.get("query")
                if ip:
                    print(f"[+] Retrieved Public IP: {ip} (via {service})")
                    return ip
        except Exception:
            continue
    print("[-] Could not retrieve public IP. Defaulting to automatic detection.")
    return None

def get_live_weather_open_meteo(city: str = None) -> list:
    """Fetches weather forecast using Open-Meteo API."""
    lat, lon, city_name = None, None, "Your Location"
    if city:
        print(f"[*] Geocoding city '{city}' via Open-Meteo...")
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_resp = requests.get(geo_url, timeout=10).json()
        if 'results' in geo_resp and len(geo_resp['results']) > 0:
            result = geo_resp['results'][0]
            lat = result['latitude']
            lon = result['longitude']
            city_name = result['name']
            print(f"[+] Found {city_name} at lat={lat:.4f}, lon={lon:.4f}")
        else:
            print(f"[-] Geocoding failed for '{city}'. Falling back to IP-based location.")
    
    if lat is None or lon is None:
        public_ip = get_public_ip()
        print("[*] Detecting location coordinates via IP geolocator...")
        ip_url = f"http://ip-api.com/json/{public_ip}" if public_ip else "http://ip-api.com/json/"
        ip_resp = requests.get(ip_url, timeout=5).json()
        if ip_resp.get("status") == "success":
            lat = ip_resp.get("lat")
            lon = ip_resp.get("lon")
            city_name = ip_resp.get("city")
            print(f"[+] Geolocated Location: {city_name} (lat={lat:.4f}, lon={lon:.4f})")
        else:
            lat, lon, city_name = 51.5074, -0.1278, "London (Fallback)"
            print("[-] IP geolocation failed. Falling back to London.")
            
    print(f"[*] Fetching Open-Meteo forecast for {city_name}...")
    fc_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=auto"
    fc_resp = requests.get(fc_url, timeout=10).json()
    daily = fc_resp['daily']
    
    weather_list = []
    for i in range(3):
        wcode = daily['weathercode'][i]
        low = int(round(daily['temperature_2m_min'][i]))
        high = int(round(daily['temperature_2m_max'][i]))
        wtype = map_wmo_to_watch_type(wcode)
        weather_list.append((wtype, low, high))
        print(f"  Day {i} forecast: Type={wtype} (WMO {wcode}), Min={low}°C, Max={high}°C")
        
    return weather_list

def get_live_weather_accuweather(api_key: str, city: str = None, location_key: str = None) -> list:
    """Fetches weather forecast using AccuWeather API."""
    city_name = city or "Your Location"
    
    try:
        # Step 1: Obtain location key if not provided
        if not location_key:
            if city:
                print(f"[*] Resolving city '{city}' via AccuWeather...")
                loc_url = f"http://dataservice.accuweather.com/locations/v1/cities/search?apikey={api_key}&q={city}"
                loc_resp = requests.get(loc_url, timeout=10)
                loc_resp.raise_for_status()
                loc_data = loc_resp.json()
                if isinstance(loc_data, list) and len(loc_data) > 0:
                    location_key = loc_data[0]['Key']
                    city_name = loc_data[0]['LocalizedName']
                    print(f"[+] Found Location Key: {location_key} ({city_name})")
                else:
                    raise ValueError(f"No AccuWeather location found for city: {city}")
            else:
                # Retrieve the public IP explicitly and feed it to AccuWeather IP geolocator
                public_ip = get_public_ip()
                print(f"[*] Detecting location key via AccuWeather IP geolocator (using IP: {public_ip or 'auto'})...")
                loc_url = f"http://dataservice.accuweather.com/locations/v1/cities/ipaddress?apikey={api_key}"
                if public_ip:
                    loc_url += f"&q={public_ip}"
                loc_resp = requests.get(loc_url, timeout=10)
                loc_resp.raise_for_status()
                loc_data = loc_resp.json()
                location_key = loc_data['Key']
                city_name = loc_data['LocalizedName']
                print(f"[+] Detected Location Key: {location_key} ({city_name})")
        
        # Step 2: Fetch 5-day daily forecast
        print(f"[*] Fetching AccuWeather 5-day daily forecast for {city_name} (Key: {location_key})...")
        fc_url = f"http://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}?apikey={api_key}&metric=true"
        fc_resp = requests.get(fc_url, timeout=10)
        fc_resp.raise_for_status()
        fc_data = fc_resp.json()
        
        daily_forecasts = fc_data['DailyForecasts']
        weather_list = []
        for i in range(3):
            day_data = daily_forecasts[i]
            low = int(round(day_data['Temperature']['Minimum']['Value']))
            high = int(round(day_data['Temperature']['Maximum']['Value']))
            icon_id = day_data['Day']['Icon']
            wtype = map_accuweather_icon_to_watch_type(icon_id)
            weather_list.append((wtype, low, high))
            print(f"  Day {i} forecast: Type={wtype} (AccuWeather Icon {icon_id}), Min={low}°C, Max={high}°C")
            
        return weather_list
    except Exception as e:
        print(f"[-] AccuWeather API error: {e}. Falling back to Open-Meteo.")
        return get_live_weather_open_meteo(city)

async def main():
    global client_ref
    
    # Setup Argument Parser
    parser = argparse.ArgumentParser(description="Watch Weather Sync Tool (with Open-Meteo & AccuWeather)")
    parser.add_argument('--mac', default=MAC_ADDRESS, help=f"Watch Bluetooth MAC address (default: {MAC_ADDRESS})")
    parser.add_argument('--city', type=str, help="Name of city to fetch real-world weather forecast for")
    parser.add_argument('--accuweather-key', type=str, default=os.getenv('ACCUWEATHER_API_KEY'),
                        help="AccuWeather API key (can also be set via ACCUWEATHER_API_KEY env var)")
    parser.add_argument('--accuweather-location-key', type=str,
                        help="Skip location search by providing a pre-resolved AccuWeather Location Key")
    
    # Manual shortcuts
    weather_shortcuts = ['sunny', 'cloudy', 'rainy', 'overcast', 'snowy', 'windy', 'stormy', 'foggy']
    for ws in weather_shortcuts:
        parser.add_argument(f'--{ws}', nargs=3, type=float, metavar=('CUR', 'HIGH', 'LOW'),
                            help=f"Manually set weather to {ws} with: current, high, low temp")
        
    args = parser.parse_args()
    
    # Resolve weather list
    weather_list = []
    manual_provided = False
    
    for ws in weather_shortcuts:
        val = getattr(args, ws)
        if val is not None:
            manual_provided = True
            w_type = WEATHER_MAP[ws]
            cur_t, high_t, low_t = val
            print(f"[+] Using manual {ws} weather parameters: Current={cur_t}°C, High={high_t}°C, Low={low_t}°C")
            # Build identical forecast for 3 days from manual parameters
            weather_list = [(w_type, int(low_t), int(high_t)) for _ in range(3)]
            break
            
    if not manual_provided:
        # Fetch live forecast
        if args.accuweather_key:
            print("[*] AccuWeather API Key detected. Using AccuWeather engine...")
            weather_list = get_live_weather_accuweather(args.accuweather_key, args.city, args.accuweather_location_key)
        else:
            print("[*] No AccuWeather API Key detected. Using Open-Meteo engine...")
            weather_list = get_live_weather_open_meteo(args.city)
        
    # Build the 19-byte 3-day weather payload
    weather_payload = build_weather_payload_3day(weather_list)
    
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

        # 2. Device Sync (Opcode 9)
        print("[>] Sending Device Sync (0x09)...")
        dev_sync_chunks = build_master_packet(0, 1, 0x09, b"\x01")
        await send_command(dev_sync_chunks, "Device Sync")
        await asyncio.sleep(0.5)

        # 3. App Sync (Opcode 110 / 0x6E)
        print("[>] Sending App Sync (0x6E)...")
        app_sync_chunks = build_master_packet(0, 1, 0x6E, b"\x01")
        await send_command(app_sync_chunks, "App Sync")
        await asyncio.sleep(0.5)

        # 4. Push 3-Day Weather (Opcode 105 / 0x69)
        print("[>] Pushing 3-Day Weather Update (0x69)...")
        weather_chunks = build_master_packet(0, 1, 0x69, weather_payload)
        await send_command(weather_chunks, "Weather Update")
        
        print("[+] Weather sync completed successfully! Keeping connection alive for 3s...")
        await asyncio.sleep(3.0)
        
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
