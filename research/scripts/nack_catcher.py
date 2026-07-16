import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

# We send a packet with a 'High-Value Opcode' (0xFF) 
# and watch how the watch error-handler responds.
def build_nack_packet():
    # Header AB + Len 0011 + Opcode FF (Invalid) + Sub 0x01
    p = bytearray([0xAB, 0x00, 0x11, 0xFF, 0x01])
    p.extend([0x00] * 14)
    p.append(sum(p) & 0xFF)
    return bytes(p)

def callback(sender, data):
    # If the watch is in a debug-ready state, it will dump 
    # the offending Opcode or a '0x00' error code.
    print(f"[ERROR_RESPONSE] {data.hex().upper()}")

async def run():
    async with BleakClient(MAC) as client:
        await client.start_notify(TX_NOTIFY, callback)
        print("[!] Injecting Malformed Opcode (0xFF)...")
        await client.write_gatt_char(RX_WRITE, build_nack_packet(), response=False)
        await asyncio.sleep(2.0)

if __name__ == "__main__":
    asyncio.run(run())
