import asyncio
import datetime
import sys
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

last_telemetry = ""

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
    global last_telemetry
    hex_str = data.hex().upper()
    
    # Filter out redundant trailing ACKs to isolate true register hits
    if hex_str != last_telemetry:
        print(f"  [!] TELEMETRY CHANGE -> {hex_str}", flush=True)
        last_telemetry = hex_str
    else:
        print(f"      (Echo ACK: ...{hex_str[-4:]})", flush=True)

async def run():
    print(f"Connecting to watch platform at {MAC}...", flush=True)
    async with BleakClient(MAC, timeout=20.0) as client:
        await client.start_notify(TX_NOTIFY, callback)
        
        # --- PHASES 1-7: MASTER AUTHENTICATION ---
        print("[+] Establishing Master Authentication (Phases 1-7)...", flush=True)
        now = datetime.datetime.now()
        
        await client.write_gatt_char(RX_WRITE, build_fixed_packet(0x0C, 0x07, bytearray([now.year % 100, now.month, now.day, now.hour, now.minute, now.second]), 26), response=False)
        await asyncio.sleep(0.6)
        await client.write_gatt_char(RX_WRITE, build_fixed_packet(0x0A, 0x01, bytearray([0x02]) + b"Raspbi", 20), response=False)
        await asyncio.sleep(0.6)
        await client.write_gatt_char(RX_WRITE, build_fixed_packet(0x0C, 0x05, bytearray([0x01]), 20), response=False)
        await asyncio.sleep(0.5)
        await client.write_gatt_char(RX_WRITE, build_fixed_packet(0x0C, 0x03, bytearray([0x00, 0x00, 0x00]), 20), response=False)
        await asyncio.sleep(0.5)
        await client.write_gatt_char(RX_WRITE, build_fixed_packet(0x0C, 0x01, bytearray([0x00, 0x19, 0xAF, 0x46, 0x27, 0x10]), 20), response=False)
        await asyncio.sleep(0.5)
        await client.write_gatt_char(RX_WRITE, build_fixed_packet(0x0C, 0x02, bytearray([0x01]), 20), response=False)
        await asyncio.sleep(0.6)
        await client.write_gatt_char(RX_WRITE, build_fixed_packet(0x0C, 0x06, bytearray([0x01]), 20), response=False)
        await asyncio.sleep(1.0)
        
        print("[+] Bridge Authenticated! Enabling Message Switch (0x0C 0x08)...")
        await client.write_gatt_char(RX_WRITE, build_fixed_packet(0x0C, 0x08, bytearray([0x01]), 20), response=False)
        await asyncio.sleep(1.5)

        # --- PHASE 8: THE REAL ACTUATOR SWEEP (Master 0x0C | Sub-Opcodes 0x09 to 0x25) ---
        print("\n" + "="*60)
        print("[!] STARTING REAL ACTUATOR SWEEP (Master 0x0C | Sub 0x09 to 0x25)")
        print("[!] Look at the screen, listen for buzzes, and watch the green sensor LED!")
        print("="*60)

        for sub_op in range(0x09, 0x26):
            # Passing a 1-byte active flag (0x01) to trigger toggles/actuators
            test_pkt = build_fixed_packet(0x0C, sub_op, bytearray([0x01]), 20)
            print(f"\n[SWEEP] Testing Master 0x0C | Sub-Opcode 0x{sub_op:02X} -> {test_pkt.hex().upper()}")
            
            await client.write_gatt_char(RX_WRITE, test_pkt, response=False)
            
            # 3-second observation window so you can feel vibrations or see screen reactions
            await asyncio.sleep(3.0)

        print("\n[*] Sweep complete. Closing channel...")
        await asyncio.sleep(2.0)
        await client.stop_notify(TX_NOTIFY)

if __name__ == "__main__":
    asyncio.run(run())
