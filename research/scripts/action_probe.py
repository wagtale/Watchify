import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

def build_packet(opcode, payload_data):
    packet = bytearray([0xAB])
    total_len = 1 + len(payload_data)
    packet.append((total_len >> 8) & 0xFF)
    packet.append(total_len & 0xFF)
    packet.append(opcode)
    packet.extend(payload_data)
    packet.append(sum(packet) & 0xFF)
    return bytes(packet)

def callback(sender, data):
    print(f"\n[Watch Telemetry] Handle 17: {data.hex().upper()}", flush=True)

async def run():
    print(f"Connecting to hardware interface...", flush=True)
    async with BleakClient(MAC) as client:
        await client.start_notify(TX_NOTIFY, callback)
        print("[+] Direct connection established.", flush=True)
        
        # 1. Fire a standard status handshake query
        init_matrix = bytearray([0x01, 0x02, 0x00, 0x01, 0xE2, 0x40, 0x00, 0x00, 0x00, 0x00])
        init_packet = build_packet(0x01, init_matrix)
        print(f"[->] Initializing core stack...")
        await client.write_gatt_char(RX_WRITE, init_packet, response=False)
        await asyncio.sleep(0.5)
        
        # 2. Fire the 'Find My Watch' Vibration command (Opcode 0x04, Sub-Opcode 0x01)
        # This bypasses full UI binding because it is an urgent proximity tracking function
        vibe_matrix = bytearray([0x01]) 
        vibe_packet = build_packet(0x04, vibe_matrix)
        
        print(f"[->] Blasting Proximity Motor Driver Command: {vibe_packet.hex().upper()}")
        await client.write_gatt_char(RX_WRITE, vibe_packet, response=False)
        
        print("[*] Holding channel open. Check if the watch motor triggers physical vibration...")
        await asyncio.sleep(5.0)
        await client.stop_notify(TX_NOTIFY)

if __name__ == "__main__":
    asyncio.run(run())
