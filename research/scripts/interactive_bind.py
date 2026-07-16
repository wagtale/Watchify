import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
TX_NOTIFY = "0000b001-0000-1000-8000-00805f9b34fb"
RX_WRITE  = "0000b002-0000-1000-8000-00805f9b34fb"

def callback(sender, data):
    print(f"\n[!!!] WATCH BROADCAST: {data.hex().upper()}", flush=True)
    if data.hex().upper().startswith("00FF01") or "0104" in data.hex().upper():
        print("\n[+] SUCCESS! PAIRING KEY CONFIRMED BY WATCH FIRMWARE!", flush=True)

async def run():
    print(f"Connecting to hardware interface at {MAC}...", flush=True)
    async with BleakClient(MAC, timeout=20.0) as client:
        print("[+] Connection established. Subscribing to RX notification pipe...", flush=True)
        await client.start_notify(TX_NOTIFY, callback)
        
        # Deploying the validated binding matrix string
        # AB (Header) + 000B (Len) + 01 (Op) + 01 (Bind SubOp) + 02 (Android) + UserID + Padding + DD (CRC)
        bind_packet = bytes.fromhex("AB000B0101020001E24000000000DD")
        
        print(f"\n[->] Blasting Bind Token: {bind_packet.hex().upper()}")
        print("[*] CRITICAL: Look at the watch face immediately after this text!", flush=True)
        
        await client.write_gatt_char(RX_WRITE, bind_packet, response=False)
        
        # Hold the pipeline open for 30 seconds to allow physical interaction
        print("\n[*] Connection locked open. If the watch face lights up, vibrates,")
        print("[*] or displays a pairing ring/icon, TAP or LONG-PRESS it now...")
        
        countdown = 30
        for i in range(countdown, 0, -1):
            sys.stdout.write(f"\rTime remaining to confirm on watch face: {i}s  ")
            sys.stdout.flush()
            await asyncio.sleep(1.0)
            
        print("\n\n[-] Session window expired. Disconnecting hardware handler...", flush=True)
        await client.stop_notify(TX_NOTIFY)

if __name__ == "__main__":
    import sys
    asyncio.run(run())
