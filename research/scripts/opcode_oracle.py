import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

# We use an empty 20-byte packet that is mathematically valid
def build_packet(opcode):
    p = bytearray([0xAB, 0x00, 0x11, opcode, 0x01]) # Opcode + Sub 0x01
    p.extend([0x00] * 14) # Padding to 20 bytes
    p.append(sum(p) & 0xFF) # CRC
    return bytes(p)

async def run():
    async with BleakClient(MAC) as client:
        print("[!] Starting Opcode Oracle Sweep. Watch for unique ACKs.")
        for op in range(1, 256):
            pkt = build_packet(op)
            await client.write_gatt_char(RX_WRITE, pkt, response=False)
            print(f"Testing Opcode 0x{op:02X}...", end="\r")
            await asyncio.sleep(0.3)

if __name__ == "__main__":
    asyncio.run(run())
