import asyncio
import sys
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

def calculate_checksum(packet_bytes):
    return sum(packet_bytes) & 0xFF

def callback(sender, data):
    print(f"\n[!!!] DISCOVERY: Data back -> {data.hex().upper()}", flush=True)

async def run():
    print(f"Connecting to lock onto active protocol channel...", flush=True)
    async with BleakClient(MAC) as client:
        await client.start_notify(TX_NOTIFY, callback)
        
        # Opcodes that successfully shattered the silence in your first run
        responsive_opcodes = [0x0A, 0x0C, 0x10, 0x12, 0x19, 0x1E, 0x2B, 0x32, 0x34]
        
        print("[*] Channel verified. Testing structural binding formats...", flush=True)
        
        for op in responsive_opcodes:
            # Struct 1: Standard 7-byte binding framing [Header, Len, Op, SubOp, Data0, Data1, Checksum]
            p1 = bytearray([0xAB, 0x00, 0x05, op, 0x01, 0x00, 0x00])
            p1.append(calculate_checksum(p1))
            
            # Struct 2: Key registration framing [Header, Len, Op, ProtocolType, Key0, Key1, Checksum]
            p2 = bytearray([0xAB, 0x00, 0x06, op, 0x01, 0x01, 0x01, 0x00])
            p2.append(calculate_checksum(p2))
            
            for test_pack in [p1, p2]:
                print(f"Firing Matrix -> Op: 0x{op:02X} Payload: {test_pack.hex().upper()}", flush=True)
                await client.write_gatt_char(RX_WRITE, bytes(test_pack), response=False)
                await asyncio.sleep(0.4) # Slightly longer pause to read complex changes
                
        print("[*] Batch run completed. Monitoring data pipeline...", flush=True)
        await asyncio.sleep(4.0)

if __name__ == "__main__":
    asyncio.run(run())
