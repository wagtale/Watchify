import asyncio
import struct
import sys
import time
from bleak import BleakClient

MAC_ADDRESS = "A1:B2:CC:09:78:0F"
WRITE_UUID  = "0000b002-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000b001-0000-1000-8000-00805f9b34fb"

# ... [Keep the same build_master_packet and get_notice_payload functions as in v16] ...

async def run_automated_test():
    # ... [After Unlock] ...
    print("\n[*] TEST 0: Enabling Master Notification Switch (Opcode 0x7C)...")
    # Toggle switch ON: Send 0x01 (ON)
    switch_chunks = build_master_packet(0, 1, 0x7C, b"\x01")
    await send_command(switch_chunks, "Notification Master Switch ON")
    await asyncio.sleep(1.0)
    
    # ... [Then run TEST 1 & TEST 2 as before] ...
