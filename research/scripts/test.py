import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
WRITE_UUID = "0000b002-0000-1000-8000-00805f9b34fb"

# The handshake to keep the watch unlocked
BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

async def main():
    print(f"[*] Connecting to watch to experiment with screen modes...")
    try:
        async with BleakClient(MAC, timeout=12.0) as client:
            if client.is_connected:
                print("[+] Connected. Authenticating...")
                await client.write_gatt_char(WRITE_UUID, BIND_PAYLOAD, response=False)
                await asyncio.sleep(0.8)
                
                # Let's test a different UI alert type (e.g., changing 0404 to 0401 or 0402)
                # In many variants, 0401 = Incoming Call Screen, 0402 = SMS Notification display
                EXPERIMENTAL_OPCODE = "01" 
                
                payload = bytearray.fromhex("00ff000304000000010001000000000000000000")
                payload[5] = int(EXPERIMENTAL_OPCODE, 16) # Swap out the sub-opcode byte
                
                print(f"[!] Sending experimental screen command: {payload[4:6].hex().upper()}")
                await client.write_gatt_char(WRITE_UUID, bytes(payload), response=False)
                
                print("[+] Done. Watch the screen to see what layout appears!")
            else:
                print("[-] Connection failed.")
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
