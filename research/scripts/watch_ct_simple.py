import asyncio
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

async def handler(sender, data):
    print(f"[<<<] Received: {data.hex()}")

async def main():
    async with BleakClient(MAC_ADDRESS) as client:
        await client.start_notify(NOTIFY_UUID, handler)
        print("[>] Sending Minimal Bind Request...")
        # Minimal bind opcode 0x01
        await client.write_gatt_char(WRITE_UUID, b"\x00\x03\x01\x00\x00", response=False)
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
