#!/usr/bin/env python3
import asyncio
import struct
import sys
import time
import argparse
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

FULL_BIND_PAYLOAD = bytes.fromhex(
    "00000300016e000038003600080c006690fc5fb4010021aa3c00040067000c006848ff"
    "536a201c0002000004006d0104007a0104007b0108007c01ff07000005007801000000"
    "00000000000000000000"
)

client_ref = None
pid_counter = 0
time_sync_done = asyncio.Event()

# Mappings of bits in the 32-bit App Switch bitmask
APP_BITS = {
    'qq': 0,
    'wechat': 1,
    'email': 2,
    'facebook': 3,
    'twitter': 4,
    'whatsapp': 5,
    'instagram': 6,
    'skype': 7,
    'linkedin': 8,
    'line': 9,
    'other': 10
}

def build_master_packet(i: int, i2: int, opcode: int, payload: bytes) -> list[bytes]:
    global pid_counter
    length = len(payload)
    if length <= 10:
        pkt = bytearray(20)
        pkt[0] = 0x00
        pkt[1] = pid_counter & 0xFF
        pkt[2] = 0x00
        pkt[3] = i & 0xFF
        pkt[4] = i2 & 0xFF
        pkt[5] = opcode & 0xFF
        pkt[8:10] = struct.pack("<H", length)
        pkt[10:10+length] = payload
        pid_counter = (pid_counter + 1) % 256
        return [bytes(pkt)]
    else:
        remaining = length - 10
        add_frags = remaining // 19 + (1 if remaining % 19 > 0 else 0)
        total_size = (add_frags * 20) + 20
        buffer = bytearray(total_size)
        buffer[0] = 0x00
        buffer[1] = pid_counter & 0xFF
        buffer[2] = add_frags & 0xFF
        buffer[3] = i & 0xFF
        buffer[4] = i2 & 0xFF
        buffer[5] = opcode & 0xFF
        buffer[8:10] = struct.pack("<H", length)
        buffer[10:20] = payload[:10]
        for f in range(add_frags):
            offset = (f + 1) * 20
            buffer[offset] = f + 1
            start = 10 + (f * 19)
            end = min(start + 19, length)
            buffer[offset + 1 : offset + 1 + (end - start)] = payload[start : end]
        pid_counter = (pid_counter + 1) % 256
        return [bytes(buffer[idx:idx+20]) for idx in range(0, total_size, 20)]

def get_time_sync_payload() -> bytes:
    return struct.pack("<IIB", int(time.time()), 7200, 0x01)

async def send_command(chunks: list[bytes], label: str):
    for idx, chunk in enumerate(chunks):
        await client_ref.write_gatt_char(WRITE_UUID, chunk, response=False)
        print(f"[>] Sent {label} (Chunk {idx+1}/{len(chunks)}): {chunk.hex()}")
        if len(chunks) > 1:
            await asyncio.sleep(0.05)

async def telemetry_handler(sender, data: bytearray):
    if len(data) >= 3 and data[0] == 0x00 and data[2] == 0x0C:
        print("[!] Sync Request received from Watch. Sending Time Sync...")
        await send_command(build_master_packet(0, 1, 0x0C, get_time_sync_payload()), "Time Sync")
        time_sync_done.set()
    elif len(data) >= 4 and data[0] == 0x00 and data[2] == 0x00:
        acked_opcode = data[3]
        print(f"[<] Watch acknowledged Opcode 0x{acked_opcode:02X}")
        if acked_opcode == 0x0C:
            time_sync_done.set()

async def main():
    global client_ref
    
    parser = argparse.ArgumentParser(description="Watch Notification Toggles Sync Tool")
    parser.add_argument('--mac', default=MAC_ADDRESS, help=f"Watch MAC (default: {MAC_ADDRESS})")
    
    # Switch targets
    parser.add_argument('--calls', type=int, choices=[0, 1], help="Enable (1) or Disable (0) Incoming Call notifications")
    parser.add_argument('--sms', type=int, choices=[0, 1], help="Enable (1) or Disable (0) SMS notifications")
    
    # App switches
    parser.add_argument('--master-app', type=int, choices=[0, 1], help="Enable (1) or Disable (0) master app notification toggle")
    parser.add_argument('--enable-apps', nargs='+', choices=APP_BITS.keys(), help="App names to enable")
    parser.add_argument('--disable-apps', nargs='+', choices=APP_BITS.keys(), help="App names to disable")
    
    args = parser.parse_args()
    
    commands = []
    
    # Handle Call Switch (Opcode 122 / 0x7A)
    if args.calls is not None:
        print(f"[+] Call Alert Notification Toggle -> {'ON' if args.calls else 'OFF'}")
        commands.append((122, bytes([args.calls])))
        
    # Handle SMS Switch (Opcode 123 / 0x7B)
    if args.sms is not None:
        print(f"[+] SMS Alert Notification Toggle -> {'ON' if args.sms else 'OFF'}")
        commands.append((123, bytes([args.sms])))
        
    # Handle App Notification Switch (Opcode 124 / 0x7C)
    if args.master_app is not None or args.enable_apps is not None or args.disable_apps is not None:
        # Default all enabled (0x7FF) if configuring
        bitmask = 0x7FF
        
        # Apply enabling/disabling
        if args.enable_apps:
            # Start clean and add only specified
            bitmask = 0x00
            for app in args.enable_apps:
                bitmask |= (1 << APP_BITS[app])
                print(f"[+] Enabling App bit: {app}")
        if args.disable_apps:
            for app in args.disable_apps:
                bitmask &= ~(1 << APP_BITS[app])
                print(f"[-] Disabling App bit: {app}")
                
        master_val = args.master_app if args.master_app is not None else 1
        
        # Build 5-byte payload: [master_switch_byte] + [4 bytes bitmask (uint32 LE)]
        payload = bytearray([master_val])
        payload.extend(struct.pack("<I", bitmask))
        
        print(f"[+] App Notification Switch -> Master: {'ON' if master_val else 'OFF'}, Bitmask: 0x{bitmask:04X} ({bin(bitmask)})")
        commands.append((124, bytes(payload)))
        
    if not commands:
        print("[-] Error: No toggle actions specified. Run with -h for options.")
        return
        
    print(f"[*] Connecting to watch at {args.mac}...")
    async with BleakClient(args.mac, timeout=15.0) as client:
        client_ref = client
        if not client.is_connected:
            print("[-] Connection failed.")
            return
            
        print("[+] Connected! Starting notifications...")
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await asyncio.sleep(0.5)
        
        # 1. Send Binding Handshake
        print("[>] Sending binding handshake...")
        await client.write_gatt_char(WRITE_UUID, FULL_BIND_PAYLOAD, response=False)
        
        # Wait up to 3 seconds for Time Sync trigger from watch
        print("[*] Waiting for watch to request time sync...")
        try:
            await asyncio.wait_for(time_sync_done.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            print("[!] Timeout waiting for watch sync request. Sending manual Time Sync...")
            await send_command(build_master_packet(0, 1, 0x0C, get_time_sync_payload()), "Time Sync")
            
        await asyncio.sleep(0.5)

        # 2. Execute switch toggle commands
        for opcode, payload in commands:
            print(f"\n[>] Sending Switch Toggle (Opcode {opcode} / {hex(opcode)})...")
            chunks = build_master_packet(0, 1, opcode, payload)
            await send_command(chunks, f"Toggle Switch {opcode}")
            await asyncio.sleep(0.5)
        
        print("[+] Completed successfully! Keeping connection alive for 2s...")
        await asyncio.sleep(2.0)
        
        print("[*] Stopping notifications and disconnecting.")
        await client.stop_notify(NOTIFY_UUID)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[-] Fatal Error: {e}")
        sys.exit(1)
