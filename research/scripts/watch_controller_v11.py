import asyncio
import struct
import sys
from datetime import datetime
from bleak import BleakClient, BleakError

# --- CONFIGURATION ---
MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Verified 92-byte binding payload
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

# --- GLOBAL STATE MANAGEMENT ---
client_ref = None
seq_counter = 0
is_authenticated = False


# --- CRYPTOGRAPHIC & PACKET ENGINE ---
def calculate_crc16(data: bytes) -> int:
    """Calculates ZK Protocol CRC16-CCITT (Polynomial 0x8005)."""
    crc = 0
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if (crc & 0x8000):
                crc = (crc << 1) ^ 0x8005
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def build_secure_packet(opcode: int, payload: bytes = b"") -> bytes:
    """Appends Length, Rolling Sequence Number, and CRC-16 to commands."""
    global seq_counter
    seq = bytes([seq_counter % 256])
    body = seq + bytes([opcode]) + payload
    length_prefix = struct.pack("<H", len(body) + 2)
    crc = calculate_crc16(body)
    seq_counter += 1
    return length_prefix + body + struct.pack("<H", crc)


async def send_command(data: bytes, label: str = "Command"):
    """Thread-safe GATT write with error handling."""
    if not client_ref or not client_ref.is_connected:
        print("[!] Error: Not connected to watch.")
        return
    try:
        await client_ref.write_gatt_char(WRITE_UUID, data, response=False)
        # Only log manual commands or critical auth steps to keep terminal clean
        if label not in ["Sequenced Sync"]:
            print(f"\n[>] Sent {label} | Opcode: 0x{data[3]:02X} | Seq: {data[2]}")
    except Exception as e:
        print(f"\n[!] Write failed ({label}): {e}")


# --- ASYNC TELEMETRY & SECURITY HANDLER ---
async def telemetry_handler(sender, data: bytearray):
    """Background listener that resolves auth challenges and time syncs natively."""
    global is_authenticated
    if len(data) < 4:
        return
    
    opcode = data[3]  # Index 3 accounts for [Len:2][Seq:1]
    
    # 1. SECURITY CHALLENGE RESPONDER (The Key Unlock)
    if opcode == 0x09:
        print("\n[!] Auth Challenge (0x09) detected! Echoing nonce with Opcode 0x06...")
        challenge_bytes = data[4:8]
        await send_command(build_secure_packet(0x06, challenge_bytes), "Auth Response")
        is_authenticated = True
        print("[+] WATCH UNLOCKED! Operational mode active. Ready for commands.")
        print("WatchCmd > ", end="", flush=True)
        return

    # 2. TIME SYNC RESPONDER
    elif opcode == 0x0C:
        now = datetime.now()
        ts_payload = struct.pack("<HBBBBB", now.year, now.month, now.day, now.hour, now.minute, now.second)
        feature_mask = b"\x01\x01\x01\x01\x01\x01"
        await send_command(build_secure_packet(0x0C, ts_payload + feature_mask), "Sequenced Sync")
        return

    # 3. ROUTINE TELEMETRY DISPLAY
    # Hide spammy step/heartbeat opcodes once authenticated unless debugging
    if not is_authenticated or opcode not in [0x00, 0x01, 0x88, 0x16]:
        print(f"\n[<<<] Telemetry | Opcode: 0x{opcode:02X} | Data: {data[4:].hex()}")
        print("WatchCmd > ", end="", flush=True)


# --- NON-BLOCKING USER INTERFACE ---
async def interactive_shell():
    """Runs input() in a separate OS thread so Bluetooth notifications never lag."""
    print("\n--- ZK BLE CONTROLLER READY ---")
    print("Commands: 'buzz', 'text <msg>', 'status', 'exit'\n")
    
    while True:
        try:
            # Offload blocking terminal input to a background thread
            user_input = await asyncio.to_thread(input, "WatchCmd > ")
            cleaned = user_input.strip()
            if not cleaned:
                continue
            
            parts = cleaned.split(maxsplit=1)
            cmd = parts[0].lower()
            
            if cmd == "exit":
                print("[!] Shutting down session...")
                break
            elif cmd == "buzz":
                await send_command(build_secure_packet(0x74, b"\x01"), "Vibrate Motor")
            elif cmd == "text":
                if len(parts) < 2:
                    print("[!] Usage: text <message>")
                    continue
                msg_bytes = parts[1].encode('utf-8')[:32]  # Limit to 32 chars for screen buffer
                await send_command(build_secure_packet(0x9A, msg_bytes), f"Text Display ('{parts[1]}')")
            elif cmd == "status":
                state = "UNLOCKED / OPERATIONAL" if is_authenticated else "LOCKED / WAITING FOR 0x09"
                print(f"[*] Connection: Alive | Auth State: {state} | Next Seq: {seq_counter}")
            else:
                print(f"[!] Unknown command: '{cmd}'. Try 'buzz' or 'text <msg>'")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[!] Shell Error: {e}")


# --- MAIN SESSION MANAGER ---
async def main():
    global client_ref
    print(f"[>] Connecting to ZebraKing Watch ({MAC_ADDRESS})...")
    
    try:
        async with BleakClient(MAC_ADDRESS, timeout=15.0) as client:
            client_ref = client
            print("[+] Connected! Subscribing to GATT notifications...")
            await client.start_notify(NOTIFY_UUID, telemetry_handler)
            
            # Brief pause to allow GATT server to stabilize
            await asyncio.sleep(0.5)
            
            print("[>] Injecting 92-Byte Master Binding Handshake...")
            await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
            
            # Start the non-blocking command shell
            await interactive_shell()
            
            # Clean exit sequence
            await client.stop_notify(NOTIFY_UUID)
            print("[+] Notifications stopped. Disconnecting clean.")
            
    except BleakError as e:
        print(f"\n[!] Bluetooth Connection Error: {e}")
        print("[*] Tip: If 'Device busy', run `sudo hcitool ledc 64` or restart bluetooth service.")
    except Exception as e:
        print(f"\n[!] Unexpected Fatal Error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Session aborted by user (Ctrl+C). BlueZ stack cleared.")
        sys.exit(0)
