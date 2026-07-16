import asyncio
import sys
from bleak import BleakClient

# Target Watch Configuration
MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

def build_packet(opcode, payload_data):
    """
    Frames data identically to the official app protocol:
    [Header 0xAB] + [16-bit Length] + [Opcode] + [Data Payload] + [8-bit Sum Checksum]
    """
    packet = bytearray([0xAB])
    
    # Total length field counts the opcode byte + length of the data payload
    total_len = 1 + len(payload_data)
    
    # Append 16-bit length (High byte, then Low byte)
    packet.append((total_len >> 8) & 0xFF)
    packet.append(total_len & 0xFF)
    
    # Append the operational command byte and raw matrix data
    packet.append(opcode)
    packet.extend(payload_data)
    
    # Calculate and append standard 8-bit sum checksum common to these microcontrollers
    crc = sum(packet) & 0xFF
    packet.append(crc)
    
    return bytes(packet)

def callback(sender, data):
    """Triggered instantly whenever the watch's TX pipeline fires a notification."""
    print(f"\n[!!!] Pipeline Broadcast Capture: {data.hex().upper()}", flush=True)

async def main():
    print(f"Connecting to hardware interface at {MAC}...", flush=True)
    try:
        async with BleakClient(MAC, timeout=15.0) as client:
            print("[+] Direct BLE connection established.", flush=True)
            
            # Start listening to notifications immediately before sending bytes
            await client.start_notify(TX_NOTIFY, callback)
            print("[+] Notification listener active on 0x0011. Deploying payloads...", flush=True)
            
            # Strict 10-byte data payloads targeting the 0x0B length limit
            # Structure: [Sub-Opcode] + [OS Flag (02=Android)] + [4-Byte User ID] + [4-Byte Zero Padding]
            final_matrices = [
                # Matrix A: Bind Request (Sub-Op 01, OS 02, User ID 123456)
                bytearray([0x01, 0x02, 0x00, 0x01, 0xE2, 0x40, 0x00, 0x00, 0x00, 0x00]),
                
                # Matrix B: Login Request (Sub-Op 02, OS 02, User ID 123456)
                bytearray([0x02, 0x02, 0x00, 0x01, 0xE2, 0x40, 0x00, 0x00, 0x00, 0x00]),
                
                # Matrix C: Alternate Clean Token (Sub-Op 01, OS 02, Master Clear ID)
                bytearray([0x01, 0x02, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00])
            ]
            
            # Test solely against the true gateway Opcode 0x01
            for matrix in final_matrices:
                pkt = build_packet(0x01, matrix)
                print(f"\nExecuting Stream -> Op: 0x01 | Target Len: {pkt[2]:02X}")
                print(f"Full Hex String: {pkt.hex().upper()}", flush=True)
                
                # Blasting payload via Write Without Response to mimic UART stream
                await client.write_gatt_char(RX_WRITE, pkt, response=False)
                
                # Sleep between runs to allow the watch's execution loop to fire its reply
                await asyncio.sleep(2.0)
                
            print("\n[*] All sequences deployed. Monitoring active data streams for changes...", flush=True)
            await asyncio.sleep(5.0)
            
            # Clean up the notification channel before exiting
            await client.stop_notify(TX_NOTIFY)
            print("[+] Listener stopped. Session closed cleanly.")
            
    except Exception as e:
        print(f"\n[-] Connection failed or dropped: {e}", flush=True)

if __name__ == "__main__":
    # Run the asynchronous framework
    asyncio.run(main())
