import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
WRITE_UUID = "0000b002-0000-1000-8000-00805f9b34fb"

# The original working 92-byte handshake payload
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

# Verified time sync initializing vector
TIME_SYNC = bytes.fromhex("00ff000001950000080082271000000000000000")

# Verified motor trigger payload (Frame 983)
MOTOR_PAYLOAD = bytes.fromhex("00ff000204040000010001000000000000000000")

async def trigger_single_pulse(client, seq_num):
    """Performs the full authentication and alert sequence over an active link."""
    print("[+] Sending master authorization block...")
    await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
    await asyncio.sleep(0.4)
    
    print("[+] Initializing time sync layer...")
    await client.write_gatt_char(WRITE_UUID, TIME_SYNC, response=False)
    await asyncio.sleep(0.2)
    
    # Construct the motor payload with a rolling sequence tracking byte
    motor_frame = bytearray(MOTOR_PAYLOAD)
    motor_frame[3] = seq_num
    
    print(f"[!] Triggering motor haptics (Sequence: {hex(seq_num)})...")
    await client.write_gatt_char(WRITE_UUID, bytes(motor_frame), response=False)

async def main():
    print(f"[*] Opening communication link with watch [{MAC}]...")
    try:
        async with BleakClient(MAC, timeout=12.0) as client:
            if client.is_connected:
                print("[+] Connection established.")
                
                pulse_cycles = 3
                for cycle in range(pulse_cycles):
                    print(f"\n--- Starting Pulse Cycle {cycle + 1}/{pulse_cycles} ---")
                    
                    # Run the authentication and vibration sequence
                    # We increment the sequence number across cycles to satisfy the MCU counter
                    await trigger_single_pulse(client, seq_num=2 + cycle)
                    
                    if cycle < pulse_cycles - 1:
                        print(".. Waiting for motor cycle to clear ..")
                        await asyncio.sleep(2.0)
                        
                print("\n[+] All haptic loop cycles completed successfully.")
            else:
                print("[-] Failed to establish a stable link.")
    except Exception as e:
        print(f"[-] Session Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
