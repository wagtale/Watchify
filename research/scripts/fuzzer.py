import asyncio
import sys
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

def calculate_checksum(packet_bytes):
    """Calculates standard 8-bit sum checksum common in clone firmwares."""
    return sum(packet_bytes) & 0xFF

def callback(sender, data):
    print(f"\n[!!!] ALERT - RESPONSE CAUGHT from {sender}: {data.hex().upper()}", flush=True)

async def run():
    print(f"Connecting to {MAC} for protocol fuzzing...", flush=True)
    try:
        async with BleakClient(MAC, timeout=20.0) as client:
            print("[+] Connected. Starting live notification listener...", flush=True)
            await client.start_notify(TX_NOTIFY, callback)
            
            # Common clone packet headers to test
            headers = [0xAB, 0xDF, 0xDF] 
            
            print("[*] Beginning Opcode Fuzzing cycle (0x00 -> 0xFF)...", flush=True)
            
            # Fuzzing the command byte position (0 to 255)
            for opcode in range(0x00, 0x100):
                # Constructing a standard 6-byte framed payload:
                # [Header] [Length] [Opcode] [Data0] [Data1] [Checksum]
                base_packet = bytearray([0xAB, 0x00, 0x04, opcode, 0x00])
                crc = calculate_checksum(base_packet)
                base_packet.append(crc)
                
                sys.stdout.write(f"\rTesting Opcode: 0x{opcode:02X} -> Pack: {base_packet.hex().upper()}")
                sys.stdout.flush()
                
                try:
                    await client.write_gatt_char(RX_WRITE, bytes(base_packet), response=False)
                except Exception as e:
                    print(f"\n[-] TX Drop at opcode 0x{opcode:02X}: {e}")
                    break
                
                # Tiny pause so we don't saturate the microcontroller's incoming ring buffer
                await asyncio.sleep(0.05)
                
            print("\n[*] Fuzzing pass complete. Keeping listener alive for 5 seconds...", flush=True)
            await asyncio.sleep(5.0)
            await client.stop_notify(TX_NOTIFY)
            
    except Exception as e:
        print(f"\n[-] Connection error: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(run())
