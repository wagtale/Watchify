import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

def build_packet(opcode, payload_data):
    """Dynamically frames data with correct 16-bit length and trailing checksum."""
    packet = bytearray([0xAB])
    
    # Calculate length: len(opcode) + len(payload_data)
    total_len = 1 + len(payload_data)
    
    # Append 16-bit length bytes (High byte, Low byte)
    packet.append((total_len >> 8) & 0xFF)
    packet.append(total_len & 0xFF)
    
    # Append Opcode and the actual data matrix
    packet.append(opcode)
    packet.extend(payload_data)
    
    # Calculate and append standard 8-bit sum checksum
    crc = sum(packet) & 0xFF
    packet.append(crc)
    return bytes(packet)

def callback(sender, data):
    print(f"\n[!!!] DISCOVERY: Watch responded -> {data.hex().upper()}", flush=True)

async def run():
    print(f"Connecting to watch pipeline...", flush=True)
    async with BleakClient(MAC) as client:
        await client.start_notify(TX_NOTIFY, callback)
        print("[+] Link stable. Sending multi-length binding matrices...", flush=True)
        
        # We target the structural opcodes discovered in your tests
        target_opcodes = [0x0A, 0x01, 0x0C]
        
        matrices = [
            # Matrix A: Basic 7-byte Init (OS flag 0x02 for Android, followed by zeroes)
            bytearray([0x02, 0x00, 0x00]),
            
            # Matrix B: Standard 12-byte Wearfit Login string (OS flag, platform ID, dummy bonding key)
            bytearray([0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            
            # Matrix C: Extended 16-byte Pair Token (Common for modern UtraWatch clones)
            bytearray([0x02, 0x04, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00])
        ]
        
        for op in target_opcodes:
            for m in matrices:
                pkt = build_packet(op, m)
                print(f"Testing Op: 0x{op:02X} | Len Byte: {pkt[2]:02X} | Hex: {pkt.hex().upper()}", flush=True)
                await client.write_gatt_char(RX_WRITE, pkt, response=False)
                await asyncio.sleep(0.5)
                
        print("[*] Completed structural pass. Monitoring radio...", flush=True)
        await asyncio.sleep(3.0)

if __name__ == "__main__":
    asyncio.run(run())
