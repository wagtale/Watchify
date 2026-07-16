import asyncio
import struct
import sys
import time
from bleak import BleakClient, BleakError

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Verified 92-byte binding handshake
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

client_ref = None

def build_zk_command(opcode: int, payload: bytes = b"") -> bytes:
    """
    Builds single-packet ZK commands with Frag #0 (0x00):
    [0x00 (Frag #0)] + [Total Length (2B LSB)] + [Opcode (1B)] + [Payload]
    """
    total_length = len(payload) + 3
    length_prefix = struct.pack("<H", total_length)
    return b"\x00" + length_prefix + bytes([opcode]) + payload

def get_time_sync_payload() -> bytes:
    """
    Implements ProtocolAppToDevice.e(int i, long j):
    4 Bytes: Unix Timestamp in seconds (Little-Endian)
    4 Bytes: Timezone Offset in seconds (Little-Endian) -> SAST UTC+2 is 7200s
    1 Byte : Status/Feature Flag (0x01)
    """
    current_unix_sec = int(time.time())
    tz_offset_sec = 7200  # SAST (Cape Town UTC+2)
    
    # <I is 4-byte unsigned integer (Little-Endian), B is 1-byte unsigned char
    return struct.pack("<IIB", current_unix_sec, tz_offset_sec, 0x01)

def get_ai_text_payload(text: str) -> bytes:
    """
    Implements ProtocolAppToDevice.a(int i, String str) 9-byte header:
    1 Byte : Message Type Flag (0x01)
    4 Bytes: Total String Length (Little-Endian)
    4 Bytes: Offset Index (0x00000000 for short texts)
    N Bytes: UTF-8 String Data
    """
    text_bytes = text.encode('utf-8')[:32]  # Limit to 32 chars for screen buffer
    str_len = len(text_bytes)
    
    header = struct.pack("<BII", 0x01, str_len, 0)
    return header + text_bytes

async def send_command(data: bytes, label: str = "Command"):
    if not client_ref or not client_ref.is_connected:
        print("[!] Not connected.")
        return
    try:
        await client_ref.write_gatt_char(WRITE_UUID, data, response=False)
        print(f"\n[>] Sent {label} ({len(data)}B): {data.hex()}")
    except Exception as e:
        print(f"\n[!] Write failed ({label}): {e}")

async def telemetry_handler(sender, data: bytearray):
    if len(data) < 3:
        return
    
    frag_index = data[0]
    incoming_opcode = data[2] if frag_index == 0x00 and len(data) >= 3 else None

    # 1. INTERCEPT TIME SYNC REQUEST (Opcode 0x0C at Byte 2)
    if incoming_opcode == 0x0C:
        retry_num = data[3] if len(data) >= 4 else 1
        print(f"\n[!] Watch requesting Time Sync (Attempt #{retry_num}). Sending Unix Timestamp + TZ Offset...")
        
        sync_payload = get_time_sync_payload()
        sync_cmd = build_zk_command(0x0C, sync_payload)
        await send_command(sync_cmd, f"Unix Time Sync ACK (Attempt #{retry_num})")
        print("WatchCmd > ", end="", flush=True)
        return

    # 2. CONFIRM COMMAND EXECUTION (Status 0x00 at Byte 2, ACK Opcode at Byte 3)
    if incoming_opcode == 0x00 and len(data) >= 4:
        acked_opcode = data[3]
        print(f"\n[+] WATCH EXECUTION CONFIRMED! Success ACK received for Opcode 0x{acked_opcode:02X}.")
        print("WatchCmd > ", end="", flush=True)
        return

    # 3. Routine Telemetry Display (Only print Fragment 0)
    if frag_index == 0x00:
        print(f"\n[<<<] Telemetry Cycle | Raw: {data.hex()}")
        print("WatchCmd > ", end="", flush=True)

async def interactive_shell():
    print("\n--- ZK MASTER CONTROLLER READY ---")
    print("Commands: 'buzz', 'text <msg>', 'exit'\n")
    while True:
        try:
            user_input = await asyncio.to_thread(input, "WatchCmd > ")
            cleaned = user_input.strip()
            if not cleaned:
                continue
            
            parts = cleaned.split(maxsplit=1)
            cmd = parts[0].lower()
            
            if cmd == "exit":
                print("[!] Stopping session. Please wait for clean disconnect...")
                break
            elif cmd == "buzz":
                await send_command(build_zk_command(0x74, b"\x01"), "Vibrate Motor (0x74)")
            elif cmd == "text":
                if len(parts) < 2:
                    print("[!] Usage: text <message>")
                    continue
                ai_payload = get_ai_text_payload(parts[1])
                await send_command(build_zk_command(0x9A, ai_payload), f"AI Text Display ('{parts[1]}')")
            else:
                print(f"[!] Unknown command: '{cmd}'. Try 'buzz' or 'text <msg>'")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[!] Shell Error: {e}")

async def main():
    global client_ref
    async with BleakClient(MAC_ADDRESS, timeout=15.0) as client:
        client_ref = client
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await asyncio.sleep(0.5)
        print("[>] Sending 92-Byte Binding Handshake...")
        await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
        await interactive_shell()
        await client.stop_notify(NOTIFY_UUID)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
