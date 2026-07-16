import asyncio
import datetime
import sys
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

def build_fixed_packet(opcode, sub_opcode, data_payload, target_total_len):
    """
    Constructs a strict, fixed-width BLE packet matching WTWD hardware boundaries.
    """
    packet = bytearray([0xAB])
    
    # 16-bit payload length calculation
    payload_len = target_total_len - 3
    packet.append((payload_len >> 8) & 0xFF)
    packet.append(payload_len & 0xFF)
    
    # Structural headers
    packet.append(opcode)
    packet.append(sub_opcode)
    packet.extend(data_payload)
    
    # Pad out remaining buffer space with null bytes
    current_len = len(packet)
    if current_len < (target_total_len - 1):
        packet.extend([0x00] * ((target_total_len - 1) - current_len))
        
    # Calculate global arithmetic verification sum (CRC)
    crc = sum(packet) & 0xFF
    packet.append(crc)
    
    return bytes(packet)

def callback(sender, data):
    hex_str = data.hex().upper()
    print(f"\n[!!!] HFW TELEMETRY CAPTURE: {hex_str}", flush=True)
    
    # Check for terminal state progression
    if "010004" in hex_str or "0C06" in hex_str or hex_str.endswith("D5") or hex_str.endswith("CF"):
        print("\n[+++] STATE 04 ACHIEVED! Master BLE bridge permanently unlocked!", flush=True)
    elif "010003" in hex_str:
        print("[*] Watch holding Interlock State 03 — Processing setup chain...", flush=True)
    elif "00FF00" in hex_str and not "000000010002" in hex_str:
        print(f"[!] Hardware Boundary Alert: {hex_str[:12]}", flush=True)

async def run():
    print(f"Connecting to watch platform at {MAC}...", flush=True)
    async with BleakClient(MAC, timeout=20.0) as client:
        await client.start_notify(TX_NOTIFY, callback)
        
        # Phase 1: Time Sync (26 Bytes)
        print("[+] Phase 1: Synchronizing Core Clock...", flush=True)
        now = datetime.datetime.now()
        year_byte = now.year % 100 
        time_data = bytearray([year_byte, now.month, now.day, now.hour, now.minute, now.second])
        time_packet = build_fixed_packet(0x0C, 0x07, time_data, 26)
        print(f"[->] Pushing Time Frame (26B): {time_packet.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, time_packet, response=False)
        await asyncio.sleep(1.2) 
        
        # Phase 2: Named Handshake (20 Bytes)
        print("\n[+] Phase 2: Injecting Named Bind Request ('Raspbi')...", flush=True)
        bind_data = bytearray([0x02]) + bytearray(b"Raspbi")
        bind_packet = build_fixed_packet(0x0A, 0x01, bind_data, 20)
        print(f"[->] Pushing Handshake (20B):  {bind_packet.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, bind_packet, response=False)
        await asyncio.sleep(1.2)

        # Phase 3: Language Configuration (20 Bytes) -> Sub-Opcode 0x05
        print("\n[+] Phase 3: Setting UI Language (English / 20B)...", flush=True)
        lang_packet = build_fixed_packet(0x0C, 0x05, bytearray([0x01]), 20)
        print(f"[->] Pushing Language (20B):   {lang_packet.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, lang_packet, response=False)
        await asyncio.sleep(1.2)

        # Phase 4: Measurement Units Configuration (20 Bytes) -> Sub-Opcode 0x03
        print("\n[+] Phase 4: Setting Measurement Units (Metric / 24h / 20B)...", flush=True)
        units_packet = build_fixed_packet(0x0C, 0x03, bytearray([0x00, 0x00, 0x00]), 20)
        print(f"[->] Pushing Units (20B):      {units_packet.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, units_packet, response=False)
        await asyncio.sleep(1.2)

        # Phase 5: Baseline User Profile (20 Bytes) -> Sub-Opcode 0x01
        print("\n[+] Phase 5: Injecting Baseline User Profile (20B)...", flush=True)
        user_data = bytearray([0x00, 0x19, 0xAF, 0x46, 0x27, 0x10])
        user_packet = build_fixed_packet(0x0C, 0x01, user_data, 26) # Clamped to 20B in logic below
        user_packet = build_fixed_packet(0x0C, 0x01, user_data, 20)
        print(f"[->] Pushing User Profile (20B): {user_packet.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, user_packet, response=False)
        await asyncio.sleep(1.2)

        # Phase 6: App Sync Interlock Gate (20 Bytes) -> Sub-Opcode 0x02
        # Satisfies the mandatory pre-finish synchronization requirement in 20B format
        print("\n[+] Phase 6: Deploying DATA_TYPE_APP_SYNC Gate (20B)...", flush=True)
        sync_packet = build_fixed_packet(0x0C, 0x02, bytearray([0x01]), 20)
        print(f"[->] Pushing App Sync (20B):   {sync_packet.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, sync_packet, response=False)
        await asyncio.sleep(1.2)

        # Phase 7: Pair Finish Gate (20 Bytes) -> Sub-Opcode 0x06
        print("\n[+] Phase 7: Deploying DATA_TYPE_PAIR_FINISH Gate (20B)...", flush=True)
        finish_packet = build_fixed_packet(0x0C, 0x06, bytearray([0x01]), 20)
        print(f"[->] Pushing Pair Finish (20B):  {finish_packet.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, finish_packet, response=False)
        
        print("\n[*] Full 7-phase sequence deployed. Listening for master state commit...")
        await asyncio.sleep(8.0)
        await client.stop_notify(TX_NOTIFY)

if __name__ == "__main__":
    asyncio.run(run())
