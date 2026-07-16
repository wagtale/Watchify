import asyncio
import struct
import sys
from bleak import BleakClient, BleakError

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Verified 92-byte binding handshake (already pre-formatted with fragment headers 00, 01, 02, 03)
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

client_ref = None

def build_zk_command(opcode: int, payload: bytes = b"") -> bytes:
    """
    Builds single-packet ZK commands with the required GATT Fragment Index 0x00:
    [0x00 (Frag #0)] + [Total Length (2B LSB)] + [Opcode (1B)] + [Payload]
    """
    total_length = len(payload) + 3
    # <H is Little-Endian unsigned short (2 bytes)
    length_prefix = struct.pack("<H", total_length)
    return b"\x00" + length_prefix + bytes([opcode]) + payload

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
    if len(data) < 4:
        return
    
    frag_index = data[0]
    # In single-packet or fragment 0 messages, index 1-2 is length, index 3 is Opcode
    opcode = data[3] if frag_index == 0x00 and len(data) >= 4 else None

    # Handle Routine Time Sync Request (Opcode 0x0C)
    if opcode == 0x0C:
        print("\n[!] Watch requesting Time Sync. Acknowledging...")
        # Simple sync ACK payload
        sync_cmd = build_zk_command(0x0C, b"\x01\x01\x01\x01\x01\x01")
        await send_command(sync_cmd, "Time Sync ACK")
        print("WatchCmd > ", end="", flush=True)
        return

    # Print clean telemetry summary without spamming the prompt
    print(f"\n[<<<] Frag 0x{frag_index:02X} | Raw: {data.hex()}")
    print("WatchCmd > ", end="", flush=True)

async def interactive_shell():
    print("\n--- ZK FINAL CONTROLLER READY ---")
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
                break
            elif cmd == "buzz":
                # Opcode 0x74 (Vibrate), Payload 0x01 (ON)
                await send_command(build_zk_command(0x74, b"\x01"), "Vibrate Motor")
            elif cmd == "text":
                if len(parts) < 2:
                    print("[!] Usage: text <message>")
                    continue
                msg_bytes = parts[1].encode('utf-8')[:32]
                # Opcode 0x9A (Text Display)
                await send_command(build_zk_command(0x9A, msg_bytes), f"Text ('{parts[1]}')")
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
