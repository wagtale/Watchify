import asyncio
import struct
import sys
from bleak import BleakClient

# --- Hardware Configuration ---
MAC_ADDRESS = "A1:B2:CC:09:78:0F"  # Replace with your watch MAC
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# The verified 92-byte master handshake required to unlock commands and buzz motor
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

def build_padded_packet(opcode: int, payload: bytes = b"") -> bytes:
    """
    Constructs a Little-Endian packet and automatically pads it with trailing zeroes
    to an exact multiple of 20 bytes to satisfy the hardware FIFO buffer.
    """
    total_len = len(payload) + 3
    raw_packet = struct.pack("<H", total_len) + bytes([opcode]) + payload
    
    # Calculate padding required to reach nearest multiple of 20 bytes
    remainder = len(raw_packet) % 20
    if remainder != 0:
        pad_len = len(raw_packet) + (20 - remainder)
        raw_packet = raw_packet.ljust(pad_len, b"\x00")
        
    return raw_packet

def telemetry_handler(sender, data: bytearray):
    """Background listener that decodes incoming watch responses."""
    if len(data) < 5:
        return

    # Check for ZK 20-byte MTU wrapping (0x00FF)
    if data[0] == 0x00 and data[1] == 0xFF:
        true_opcode = data[5]
        payload = data[6:]
    else:
        true_opcode = data[2] if len(data) > 2 else 0
        payload = data[3:] if len(data) > 3 else b""

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

async def print_help():
    print("\n--- AVAILABLE INTERACTIVE COMMANDS ---")
    print("  text <msg>    : Push custom text to watch screen (e.g., 'text Hello Pi')")
    print("  camera <0|1>  : Trigger camera shutter (1=Enter Mode, 0=Take Photo)")
    print("  bright <0-100>: Set display backlight percentage")
    print("  hr <0|1>      : Toggle optical heart rate sensor")
    print("  buzz          : Re-trigger pairing vibration motor (Full 92B Handshake)")
    print("  info          : Query firmware version and model ID")
    print("  hex <string>  : Inject raw custom hex packet (auto-padded to 20B)")
    print("  help          : Show this menu")
    print("  exit          : Disconnect and quit")
    print("--------------------------------------\n")

async def interactive_shell(client: BleakClient):
    loop = asyncio.get_event_loop()
    await print_help()
    
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
            elif cmd == "help":
                await print_help()
            elif cmd == "buzz":
                print("[>] Triggering motor via 92-byte master block...")
                await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
            elif cmd == "info":
                print("[>] Querying hardware info (padded to 20B)...")
                await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x04, b"\x01"), response=False)
                await asyncio.sleep(0.5)
                await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x0B, b"\x01"), response=False)
            elif cmd == "text":
                if not arg:
                    print("[-] Error: Specify message (e.g., 'text Hello')")
                    continue
                print(f"[>] Pushing '{arg}' to OLED display (padded to 20B multiples)...")
                text_bytes = arg.encode("utf-8")
                await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x9A, text_bytes), response=False)
            elif cmd == "camera":
                val = 0x01 if arg == "1" else 0x00
                print(f"[>] Sending camera shutter command ({hex(val)})...")
                await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x74, bytes([val])), response=False)
            elif cmd == "bright":
                val = max(0, min(100, int(arg) if arg.isdigit() else 100))
                print(f"[>] Setting display brightness to {val}%...")
                await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x7F, bytes([val, 0x0A])), response=False)
            elif cmd == "hr":
                val = 0x01 if arg == "1" else 0x00
                print(f"[>] Toggling Heart Rate sensor ({hex(val)})...")
                await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x80, bytes([val, 0x1E])), response=False)
            elif cmd == "hex":
                try:
                    raw_bytes = bytes.fromhex(arg.replace(" ", ""))
                    padded = raw_bytes.ljust((len(raw_bytes) + 19) // 20 * 20, b"\x00")
                    print(f"[>] Injecting padded string ({len(padded)}B): {padded.hex()}...")
                    await client.write_gatt_char(WRITE_UUID, padded, response=False)
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

        # --- STEP 1: FULL 92-BYTE MASTER HANDSHAKE ---
        print("[>] Executing 92-Byte Master Handshake...")
        await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
        await asyncio.sleep(0.8)

        # --- STEP 2: PADDED CLOCK SYNC ---
        print("[>] Stabilizing RTC Clock (0x68)...")
        await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x68, bytes.fromhex("48ff536a201c00020000")), response=False)
        await asyncio.sleep(0.5)

        # --- STEP 3: VISUAL SCREEN CONFIRMATION ---
        print("[>] Pushing visual connection alert to watch screen...")
        await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x7F, bytes([100, 10])), response=False)
        await asyncio.sleep(0.3)
        
        banner = "PI CONNECTED!".encode("utf-8")
        await client.write_gatt_char(WRITE_UUID, build_padded_packet(0x9A, banner), response=False)
        await asyncio.sleep(0.5)
        
        print("[+] Watch initialized and screen notified! Entering interactive mode.")
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
