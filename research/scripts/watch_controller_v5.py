import asyncio
import struct
import sys
from bleak import BleakClient

# --- Hardware Configuration ---
MAC_ADDRESS = "A1:B2:CC:09:78:0F"  # Replace with your watch MAC
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# Verified 92-byte master handshake required to unlock command gate
FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0004007b0008007c000003000000050078010000"
    "00000000000000000000"
)

OPCODES = {
    0x04: "Firmware Version Query",
    0x0B: "Model Identification Query",
    0x68: "System Time Sync",
    0x6D: "Sensor & Battery Status",
    0x74: "Remote Camera Shutter",
    0x78: "Pairing Master Handshake",
    0x7A: "Notification Popup Trigger",
    0x7F: "Screen Brightness Control",
    0x80: "Optical Heart Rate Monitor",
    0x9A: "AI Text Display Push",
}

async def send_command(client: BleakClient, data: bytes, label: str = "Command"):
    """
    Mimics Java SendDataRunnable: Slices data into 20-byte MTU chunks
    and enforces a 50ms inter-packet delay to prevent MCU ring buffer overflow.
    """
    chunk_size = 20
    chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
    
    if len(chunks) > 1:
        print(f"[>] Transmitting {label} ({len(data)}B across {len(chunks)} MTU slices)...")
    else:
        print(f"[>] Transmitting {label} ({len(data)}B)...")
        
    for idx, chunk in enumerate(chunks, 1):
        await client.write_gatt_char(WRITE_UUID, chunk, response=False)
        # Crucial 50ms gap allowing the wearable MCU to clear its UART ring buffer into RAM
        await asyncio.sleep(0.05)

def build_std_packet(opcode: int, payload: bytes = b"") -> bytes:
    """Standard Method c() Builder: [Len (2B Little-Endian)] + [Opcode (1B)] + [Payload]"""
    total_len = len(payload) + 3
    return struct.pack("<H", total_len) + bytes([opcode]) + payload

def build_ext_packet(opcode: int, payload: bytes = b"") -> bytes:
    """Extended Method g() Builder: [Len (2B)] + [Routing: 0x00, 0x01] + [Opcode] + [Payload]"""
    total_len = len(payload) + 5
    return struct.pack("<H", total_len) + b"\x00\x01" + bytes([opcode]) + payload

def telemetry_handler(sender, data: bytearray):
    if len(data) < 5:
        return

    if data[0] == 0x00 and data[1] == 0xFF:
        true_opcode = data[5]
        payload = data[6:]
    else:
        true_opcode = data[2] if len(data) > 2 else 0
        payload = data[3:] if len(data) > 3 else b""

    # Suppress routine background sync noise during interactive prompts
    if true_opcode in [0x00, 0x01, 0x09, 0x6E] and len(payload) > 8:
        return

    op_label = OPCODES.get(true_opcode, f"Opcode 0x{true_opcode:02X}")
    print(f"\n[<<< WATCH TELEMETRY] {op_label}")
    print(f"  ├── Raw Hex: {payload.hex()}")
    
    if true_opcode == 0x04 or (len(payload) >= 5 and payload[:2] == b"\x00\x00"):
        v = payload
        print(f"  └── Decoded: Firmware v{v[2]}.{v[3]}.{v[4]}.{v[5]}")
    elif true_opcode == 0x0B:
        txt = payload.decode("utf-8", errors="ignore").rstrip("\x00").strip()
        print(f"  └── Decoded: Model -> '{txt}'")
    
    print("WatchCmd > ", end="", flush=True)

async def interactive_shell(client: BleakClient):
    loop = asyncio.get_event_loop()
    print("\n--- AVAILABLE INTERACTIVE COMMANDS ---")
    print("  text <msg>    : Push custom text via Extended g(0,1) routing")
    print("  camera <0|1>  : Trigger remote camera shutter")
    print("  bright <0-100>: Set display brightness percentage & wake screen")
    print("  hr <0|1>      : Toggle optical heart rate sensor")
    print("  buzz          : Re-trigger pairing vibration motor (Paced 92B Block)")
    print("  info          : Query firmware version and model ID")
    print("  raw <hex>     : Inject custom hex via Extended g(0,1) routing")
    print("  exit          : Disconnect and quit")
    print("--------------------------------------\n")
    
    # Flush Linux terminal input buffer to prevent swallowed keystrokes
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except (ImportError, Exception):
        pass
    
    while client.is_connected:
        try:
            user_input = await loop.run_in_executor(None, input, "WatchCmd > ")
            parts = user_input.strip().split(maxsplit=1)
            if not parts:
                continue
                
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ["exit", "quit"]:
                print("[*] Closing link...")
                break
            elif cmd == "buzz":
                await send_command(client, FULL_BIND_PAYLOAD, "Master Vibration Handshake")
            elif cmd == "info":
                await send_command(client, build_std_packet(0x04, b"\x01"), "Firmware Query")
                await asyncio.sleep(0.4)
                await send_command(client, build_std_packet(0x0B, b"\x01"), "Model ID Query")
            elif cmd == "text":
                if not arg:
                    print("[-] Error: Specify message (e.g., 'text Hello')")
                    continue
                text_bytes = arg.encode("utf-8")
                await send_command(client, build_ext_packet(0x9A, text_bytes), f"OLED Text Push ('{arg}')")
            elif cmd == "camera":
                val = 0x01 if arg == "1" else 0x00
                await send_command(client, build_ext_packet(0x74, bytes([val])), f"Camera Shutter ({hex(val)})")
            elif cmd == "bright":
                val = max(0, min(100, int(arg) if arg.isdigit() else 100))
                await send_command(client, build_ext_packet(0x7F, bytes([val, 0x0A])), f"Brightness ({val}%)")
            elif cmd == "hr":
                val = 0x01 if arg == "1" else 0x00
                await send_command(client, build_ext_packet(0x80, bytes([val, 0x1E])), f"HR Sensor Toggle ({hex(val)})")
            elif cmd == "raw":
                try:
                    raw_bytes = bytes.fromhex(arg.replace(" ", ""))
                    packet = build_ext_packet(raw_bytes[0], raw_bytes[1:])
                    await send_command(client, packet, f"Raw Extended Injection ({len(packet)}B)")
                except ValueError:
                    print("[-] Error: Invalid hex string.")
            else:
                print(f"[-] Unknown command '{cmd}'. Type 'help' for options.")
                
        except Exception as e:
            print(f"[-] Execution Error: {e}")

async def main():
    print(f"[*] Connecting to {MAC_ADDRESS}...")
    async with BleakClient(MAC_ADDRESS, timeout=15.0) as client:
        if not client.is_connected:
            print("[-] Connection failed.")
            return
            
        print("[+] Link active. Starting telemetry handler...")
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await asyncio.sleep(0.5)

        # --- STEP 1: PACED 92-BYTE MASTER HANDSHAKE ---
        await send_command(client, FULL_BIND_PAYLOAD, "92-Byte Master Handshake")
        await asyncio.sleep(1.5) # Allow 14-packet sync dump to clear radio queue

        # --- STEP 2: PACED CLOCK SYNC ---
        await send_command(client, build_std_packet(0x68, bytes.fromhex("48ff536a201c00020000")), "RTC Time Sync")
        await asyncio.sleep(0.5)

        # --- STEP 3: DUAL-MODE VISUAL WAKE ALERT ---
        print("[>] Pushing visual connection alert to watch screen...")
        await send_command(client, build_ext_packet(0x7F, bytes([100, 10])), "Screen Brightness 100%")
        await asyncio.sleep(0.2)
        
        banner = "PI CONNECTED!".encode("utf-8")
        await send_command(client, build_ext_packet(0x9A, banner), "OLED Banner Push")
        await asyncio.sleep(0.5)
        
        print("[+] Watch initialized! Entering interactive mode.")
        await interactive_shell(client)

        print("[*] Cleaning up session...")
        await client.stop_notify(NOTIFY_UUID)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Exiting control app.")
    except Exception as err:
        print(f"\n[-] Fatal Error: {err}")
