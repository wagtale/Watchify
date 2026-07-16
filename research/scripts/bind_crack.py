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
    print(f"\n[!!!] BROADCAST RECEIVED: {data.hex().upper()}", flush=True)

async def run():
    print(f"Connecting to target BLE core...", flush=True)
    async with BleakClient(MAC) as client:
        await client.start_notify(TX_NOTIFY, callback)
        print("[+] Direct channel locked. Forcing authentication matrix...", flush=True)
        
        # Focus explicitly on the two state-changing opcodes
        target_opcodes = [0x01, 0x0C]
        
        auth_matrices = [
            # Matrix 1: OS Flag (02) + Bind Flag (01) + Simulated User ID (00 01 E2 40 = 123456)
            bytearray([0x02, 0x01, 0x00, 0x01, 0xE2, 0x40, 0x00, 0x00, 0x00]),
            
            # Matrix 2: Alternative layout - Handshake Type (01) + OS (02) + User Key
            bytearray([0x01, 0x02, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00]),
            
            # Matrix 3: 6-byte padded authentication block
            bytearray([0x02, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00])
        ]
        
        for op in target_opcodes:
            for matrix in auth_matrices:
                pkt = build_packet(op, matrix)
                print(f"Injecting Op: 0x{op:02X} | Payload Structure: {matrix.hex().upper()}", flush=True)
                await client.write_gatt_char(RX_WRITE, pkt, response=False)
                await asyncio.sleep(0.8) # Giving the chip plenty of processing room
                
        print("[*] Stream sequence finished. Monitoring for authorization...", flush=True)
        await asyncio.sleep(4.0)

if __name__ == "__main__":
    asyncio.run(run())
