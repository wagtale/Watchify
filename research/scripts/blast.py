import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

# Common base commands for this architecture
TEST_PACKETS = [
    bytes.fromhex("AB0004FF0000"),  # Base OEM Link Ping
    bytes.fromhex("00"),            # Raw Single Null Byte
    bytes.fromhex("01")             # Raw Wake/Keep-alive Byte
]

def callback(sender, data):
    print(f"\n[!] RESPONSE RECEIVED: {data.hex().upper()}", flush=True)

async def run():
    print(f"Connecting to {MAC}...")
    try:
        async with BleakClient(MAC, timeout=15.0) as client:
            print("[+] Link active! Activating notifications immediately...")
            await client.start_notify(TX_NOTIFY, callback)
            
            for pkt in TEST_PACKETS:
                print(f"[->] Writing hex: {pkt.hex().upper()}")
                try:
                    # Target the RX characteristic with no response required
                    await client.write_gatt_char(RX_WRITE, pkt, response=False)
                except Exception as e:
                    print(f"[-] Write error: {e}")
                
                # Wait briefly between payloads to watch for incoming data
                await asyncio.sleep(2.0)
                
            print("[*] Packets sent. Listening a few more seconds...")
            await asyncio.sleep(3.0)
            
    except Exception as e:
        print(f"[-] Connection failed or dropped: {e}")

if __name__ == "__main__":
    asyncio.run(run())
