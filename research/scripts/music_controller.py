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

# Music action mappings from DataEnum.MusicControlType
MUSIC_ACTIONS = {
    1: "PLAY",
    2: "PAUSE",
    3: "STOP",
    4: "BACKWARD / PREVIOUS",
    5: "FORWARD / NEXT",
    6: "PLAY_OR_PAUSE_TOGGLE",
    7: "QUERY_MUSIC_INFO",
    8: "VOLUME_UP",
    9: "VOLUME_DOWN",
    10: "QUERY_VOLUME_LEVEL"
}

client_ref = None
pid_counter = 0
time_sync_done = asyncio.Event()

current_song = "Starboy - The Weeknd"
current_volume = 12  # Out of 15 (typical Android volume range)

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

def build_music_content_payload(content_type: int, content: str) -> bytes:
    """
    Constructs Opcode 113 payload conforming to ProtocolAppToDevice.j()
    Must return a 66-byte fixed-size buffer.
    """
    bArr = bytearray(66)
    bArr[0] = content_type & 0xFF
    if content_type in [8, 9, 10]:
        bArr[1] = 1  # length = 1
        bArr[2] = int(content) & 0xFF
    else:
        text_bytes = content.encode('utf-8')[:24]  # Max length limit in APK
        bArr[1] = len(text_bytes)
        bArr[2:2+len(text_bytes)] = text_bytes
    return bytes(bArr)

async def send_command(chunks: list[bytes], label: str):
    for idx, chunk in enumerate(chunks):
        await client_ref.write_gatt_char(WRITE_UUID, chunk, response=False)
        # Log packets for debugging
        # print(f"[>] Sent {label} (Chunk {idx+1}/{len(chunks)}): {chunk.hex()}")
        if len(chunks) > 1:
            await asyncio.sleep(0.05)

async def push_song_info(song: str):
    global current_song
    current_song = song
    print(f"[*] Pushing song name: '{current_song}'")
    payload = build_music_content_payload(7, current_song)
    chunks = build_master_packet(0, 1, 113, payload)
    await send_command(chunks, "Music Song Name Update")

async def push_volume_info(vol: int):
    global current_volume
    current_volume = max(0, min(15, vol))
    print(f"[*] Pushing volume level: {current_volume}/15")
    payload = build_music_content_payload(10, str(current_volume))
    chunks = build_master_packet(0, 1, 113, payload)
    await send_command(chunks, "Music Volume Level Update")

async def telemetry_handler(sender, data: bytearray):
    global current_volume, current_song
    if len(data) < 3:
        return
        
    print(f"[<] Raw Packet: {data.hex()}")

    # Determine format: standard GATT vs master-wrapped
    is_master_wrapped = (len(data) >= 6 and data[4] in [1, 4])
    
    if is_master_wrapped:
        seq_counter = data[3]
        opcode = data[5]
        direction = data[4]
    else:
        seq_counter = 0
        opcode = data[2]
        direction = 1  # Assume request

    # Check for Time Sync requests (Opcode 12 / 0x0C)
    if opcode == 12 or (data[0] == 0x00 and data[2] == 0x0C):
        print("[!] Sync Request received from Watch. Sending ACK & Time Sync Update...")
        # 1. ACK the Sync Request (direction=4, opcode=12, payload=[1])
        await send_command(build_master_packet(seq_counter, 4, 12, bytes([1])), "Sync Request ACK")
        # 2. Push actual Time Setting (direction=1, opcode=104, payload=9-bytes time details)
        await send_command(build_master_packet(0, 1, 104, get_time_sync_payload()), "Time Sync Update")
        return

    # Check for ACK responses
    if direction == 4 or (not is_master_wrapped and opcode == 0):
        acked_opcode = data[5] if is_master_wrapped else data[3]
        # Also check status byte at index 10
        status_code = data[10] if len(data) >= 11 else 0
        status_name = {1: "SUCCESS", 2: "FORMAT_ERR", 3: "CRC_ERR", 4: "QUEUE_FULL"}.get(status_code, f"CODE_{status_code}")
        print(f"[<] Watch ACK: Opcode 0x{acked_opcode:02X} -> Status: {status_name}")
        if acked_opcode == 104 or acked_opcode == 0x0C:
            time_sync_done.set()
        return

    # Check for Music Control (Opcode 14 / 0x0E)
    if opcode == 14:
        action_id = data[10] if is_master_wrapped else data[3]
        action_name = MUSIC_ACTIONS.get(action_id, f"UNKNOWN ({action_id})")
        print(f"\n[<<< MUSIC ACTION RECEIVED] {action_name} (Action ID: {action_id})")
        
        # Acknowledge the watch command (Direction=4, Opcode=14, Payload=[1])
        ack_chunks = build_master_packet(seq_counter, 4, 14, bytes([1]))
        await send_command(ack_chunks, "Music Command ACK")
        
        # Execute Action
        if action_id == 7:  # Query Music Name
            await push_song_info(current_song)
        elif action_id == 10:  # Query Volume
            await push_volume_info(current_volume)
        elif action_id == 8:  # Volume Up
            current_volume = min(15, current_volume + 1)
            await push_volume_info(current_volume)
        elif action_id == 9:  # Volume Down
            current_volume = max(0, current_volume - 1)
            await push_volume_info(current_volume)
        else:
            print(f"[🎵 MEDIA ACTION TRIGGERED] -> Action: {action_name}")
        return

async def terminal_input_loop():
    """Asynchronous console input reader to dynamically control track details."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    
    print("\n💡 Interactive Console Commands:")
    print("  - song <title>  : Set current song title and push to watch (e.g. 'song Starboy')")
    print("  - vol <0-15>    : Set current volume level and push to watch (e.g. 'vol 10')")
    print("  - exit          : Disconnect and exit")
    print("----------------------------------------------------------------------")
    
    while True:
        line = await reader.readline()
        if not line:
            break
        text = line.decode().strip()
        if not text:
            continue
            
        parts = text.split(" ", 1)
        cmd = parts[0].lower()
        
        if cmd == "exit":
            print("[*] Exit requested. Shutting down BLE link...")
            break
        elif cmd == "song" and len(parts) > 1:
            await push_song_info(parts[1])
        elif cmd == "vol" and len(parts) > 1:
            try:
                vol_val = int(parts[1])
                await push_volume_info(vol_val)
            except ValueError:
                print("[-] Error: Volume must be an integer between 0 and 15.")
        else:
            print("[-] Unknown command. Use 'song <title>', 'vol <level>', or 'exit'.")

async def main():
    global client_ref
    
    parser = argparse.ArgumentParser(description="Watch Bluetooth Music Control Server")
    parser.add_argument('--mac', default=MAC_ADDRESS, help=f"Watch MAC (default: {MAC_ADDRESS})")
    args = parser.parse_args()
    
    print(f"[*] Connecting to watch at {args.mac}...")
    async with BleakClient(args.mac, timeout=15.0) as client:
        client_ref = client
        if not client.is_connected:
            print("[-] Connection failed.")
            return
            
        print("[+] Connected! Starting notifications...")
        await client.start_notify(NOTIFY_UUID, telemetry_handler)
        await asyncio.sleep(0.5)
        
        # 1. Send Binding Handshake (enabling switches)
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

        # Sync Initial Song Info and Volume
        await push_song_info(current_song)
        await push_volume_info(current_volume)
        
        print("\n[+] Music Server listening for watch media button presses...")
        
        # Run terminal command loop concurrently
        try:
            await terminal_input_loop()
        except asyncio.CancelledError:
            pass
            
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
