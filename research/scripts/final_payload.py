import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
RX_WRITE = "0000b002-0000-1000-8000-00805f9b34fb"

async def run():
    async with BleakClient(MAC) as client:
        # 1. We don't need full auth if we just send the command within the session
        # Use the structural template found in the dump
        # AB 00 00 [Opcode] [Sub] [Data...]
        vibrate_pkt = bytes([0xAB, 0x00, 0x00, 0x07, 0x16, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        
        print("[!] Injecting Template-Matched Payload...")
        await client.write_gatt_char(RX_WRITE, vibrate_pkt, response=False)
        print("[+] Payload Sent.")

if __name__ == "__main__":
    asyncio.run(run())
