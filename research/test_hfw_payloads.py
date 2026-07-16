import asyncio
import datetime
import sys
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

def build_fixed_packet(opcode, sub_opcode, data_payload, target_total_len):
    packet = bytearray([0xAB])
    payload_len = target_total_len - 3
    packet.append((payload_len >> 8) & 0xFF)
    packet.append(payload_len & 0xFF)
    packet.append(opcode)
    packet.append(sub_opcode)
    packet.extend(data_payload)
    
    current_len = len(packet)
    if current_len < (target_total_len - 1):
        packet.extend([0x00] * ((target_total_len - 1) - current_len))
        
    crc = sum(packet) & 0xFF
    packet.append(crc)
    return bytes(packet)

def callback(sender, data):
    print(f"[ACK] Telemetry: {data.hex().upper()}", flush=True)

async def run():
    print(f"Connecting to watch platform at {MAC}...", flush=True)
    async with BleakClient(MAC, timeout=20.0) as client:
        await client.start_notify(TX_NOTIFY, callback)
        
        # --- PHASE A: RAPID AUTHENTICATION HANDSHAKE ---
        print("[+] Performing rapid HFW authorization...", flush=True)
        now = datetime.datetime.now()
        
        # 1. Time Sync (26B)
        time_pkt = build_fixed_packet(0x0C, 0x07, bytearray([now.year % 100, now.month, now.day, now.hour, now.minute, now.second]), 26)
        await client.write_gatt_char(RX_WRITE, time_pkt, response=False)
        await asyncio.sleep(0.6)
        
        # 2. Named Handshake (20B)
        bind_pkt = build_fixed_packet(0x0A, 0x01, bytearray([0x02]) + b"Raspbi", 20)
        await client.write_gatt_char(RX_WRITE, bind_pkt, response=False)
        await asyncio.sleep(0.6)
        
        # 3. App Sync Gate (20B)
        sync_pkt = build_fixed_packet(0x0C, 0x02, bytearray([0x01]), 20)
        await client.write_gatt_char(RX_WRITE, sync_pkt, response=False)
        await asyncio.sleep(1.0)

        print("[+] Bridge Authenticated in State 03! Deploying hardware payloads...\n")

        # --- PHASE B: HARDWARE VIBRATION TEST ---
        # In WTWD firmware, Opcode 0x0D or Opcode 0x04 controls immediate device alerts
        print("[!] TEST 1: Sending 'Find Watch' vibration command...")
        # Common WTWD alert triggers: Opcode 0x0D Sub 0x01 OR Opcode 0x04 Sub 0x01
        vibrate_pkt = build_fixed_packet(0x0D, 0x01, bytearray([0x01]), 20)
        print(f"[->] Pushing Vibration Trigger: {vibrate_pkt.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, vibrate_pkt, response=False)
        await asyncio.sleep(3.0)

        # --- PHASE C: OLED NOTIFICATION TEXT PUSH ---
        print("\n[!] TEST 2: Pushing custom text to watch screen...")
        # In WTWD firmware, Opcode 0x0E or 0x19 handles incoming message alerts
        # Structure: App Type (0x01=SMS/Custom) + ASCII String ("HFW LIVE")
        msg_text = b"HFW LIVE"
        msg_payload = bytearray([0x01]) + bytearray(msg_text)
        
        # Notice we use a 26-byte boundary here to accommodate text payload length
        text_pkt = build_fixed_packet(0x0E, 0x01, msg_payload, 26)
        print(f"[->] Pushing Screen Text:     {text_pkt.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, text_pkt, response=False)
        
        print("\n[*] Payloads delivered. Keep your eyes on the watch screen!")
        await asyncio.sleep(5.0)
        await client.stop_notify(TX_NOTIFY)

if __name__ == "__main__":
    asyncio.run(run())
