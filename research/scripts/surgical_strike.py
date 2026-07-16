import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
RX_WRITE = "0000b002-0000-1000-8000-00805f9b34fb"

# Template: 0x0C (System) | 0x0D (Vibration)
# We use the raw template derived from the dump
cmd = bytes([0xAB, 0x00, 0x11, 0x0C, 0x0D, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xD4])

async def run():
    async with BleakClient(MAC) as client:
        # Minimal Auth (Only the essentials to hit State 03)
        # Note: We rely on the fact that the watch is already in 'Bound' state
        print("[!] Striking...")
        await client.write_gatt_char(RX_WRITE, cmd, response=False)
        await asyncio.sleep(1.0)
        # Connection ends automatically here
        
if __name__ == "__main__":
    asyncio.run(run())
