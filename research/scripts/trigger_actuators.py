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
    print(f"[ACK] Telemetry: {hex_str}", flush=True)
    
    # Check if watch explicitly flags an actuator execution or state change
    if hex_str.endswith("CB") or hex_str.endswith("CF") or hex_str.endswith("0E"):
        pass # Standard setup progression acknowledgments
    elif "00FF00" in hex_str and not "000000010002" in hex_str and not "000000010003" in hex_str:
        print(f"      -> Hardware Response / Boundary Alert: {hex_str[:16]}", flush=True)

async def run():
    print(f"Connecting to watch platform at {MAC}...", flush=True)
    async with BleakClient(MAC, timeout=20.0) as client:
        await client.start_notify(TX_NOTIFY, callback)
        
        # --- PHASE 1-7: VERIFIED MASTER AUTHENTICATION CHAIN ---
        print("[+] Establishing Master Authentication (Phases 1-7)...", flush=True)
        now = datetime.datetime.now()
        
        # 1. Time Sync (26B)
        time_pkt = build_fixed_packet(0x0C, 0x07, bytearray([now.year % 100, now.month, now.day, now.hour, now.minute, now.second]), 26)
        await client.write_gatt_char(RX_WRITE, time_pkt, response=False)
        await asyncio.sleep(0.8)
        
        # 2. Named Handshake (20B)
        bind_pkt = build_fixed_packet(0x0A, 0x01, bytearray([0x02]) + b"Raspbi", 20)
        await client.write_gatt_char(RX_WRITE, bind_pkt, response=False)
        await asyncio.sleep(0.8)
        
        # 3. Language Config (20B) -> Sub 0x05
        lang_pkt = build_fixed_packet(0x0C, 0x05, bytearray([0x01]), 20)
        await client.write_gatt_char(RX_WRITE, lang_pkt, response=False)
        await asyncio.sleep(0.6)
        
        # 4. Measurement Units (20B) -> Sub 0x03
        units_pkt = build_fixed_packet(0x0C, 0x03, bytearray([0x00, 0x00, 0x00]), 20)
        await client.write_gatt_char(RX_WRITE, units_pkt, response=False)
        await asyncio.sleep(0.6)
        
        # 5. User Profile (20B) -> Sub 0x01
        user_pkt = build_fixed_packet(0x0C, 0x01, bytearray([0x00, 0x19, 0xAF, 0x46, 0x27, 0x10]), 20)
        await client.write_gatt_char(RX_WRITE, user_pkt, response=False)
        await asyncio.sleep(0.6)
        
        # 6. App Sync Gate (20B) -> Sub 0x02
        sync_pkt = build_fixed_packet(0x0C, 0x02, bytearray([0x01]), 20)
        await client.write_gatt_char(RX_WRITE, sync_pkt, response=False)
        await asyncio.sleep(0.8)
        
        # 7. Pair Finish Gate (20B) -> Sub 0x06
        finish_pkt = build_fixed_packet(0x0C, 0x06, bytearray([0x01]), 20)
        await client.write_gatt_char(RX_WRITE, finish_pkt, response=False)
        await asyncio.sleep(1.0)
        
        print("[+] Bridge Authenticated! Unlocking notification registers...\n")

        # --- PHASE 8: ENABLE MESSAGE SWITCH INTERLOCK ---
        # DATA_TYPE_MESSAGE_SWITCH (Opcode 0x0C, Sub-Opcode 0x08) -> Set to 0x01 (Enabled)
        print("[!] STEP 1: Enabling OLED Message Switch register (Sub 0x08)...")
        switch_pkt = build_fixed_packet(0x0C, 0x08, bytearray([0x01]), 20)
        print(f"[->] Pushing Switch:   {switch_pkt.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, switch_pkt, response=False)
        await asyncio.sleep(1.2)

        # --- PHASE 9: VIBRATION ACTUATOR TEST ---
        # DATA_TYPE_FIND_PHONE_OR_DEVICE (Opcode 0x07, Sub-Opcode 0x01) -> Pulse Motor
        print("\n[!] STEP 2: Sending Vibration Actuator command ('Find Watch')...")
        vibrate_pkt = build_fixed_packet(0x07, 0x01, bytearray([0x01]), 20)
        print(f"[->] Pushing Vibrate:  {vibrate_pkt.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, vibrate_pkt, response=False)
        await asyncio.sleep(3.0)

        # --- PHASE 10: OLED NOTIFICATION TEXT PUSH ---
        # DATA_TYPE_MESSAGE_NOTICE (Opcode 0x19, Sub-Opcode 0x01) -> Push ASCII String
        print("\n[!] STEP 3: Pushing 'HFW LIVE' notification text to OLED screen...")
        msg_text = b"HFW LIVE"
        msg_payload = bytearray([0x01]) + bytearray(msg_text)
        
        # Using 26B boundary to accommodate string length payload
        text_pkt = build_fixed_packet(0x19, 0x01, msg_payload, 26)
        print(f"[->] Pushing Text:     {text_pkt.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, text_pkt, response=False)
        
        print("\n[*] All actuator streams deployed. Keep your eyes on the watch screen!")
        await asyncio.sleep(6.0)
        await client.stop_notify(TX_NOTIFY)

if __name__ == "__main__":
    asyncio.run(run())
