import asyncio
from bleak import BleakClient

MAC = "A1:B2:CC:09:78:0F"
RX_WRITE = "0000b002-0000-1000-8000-00805f9b34fb"

# Master Opcodes found in your dump that look like command channels
MASTER_OPCODES = [0x0C, 0x07, 0x0D, 0x19]

def build_packet(opcode, sub_op):
    # AB 00 11 [Opcode] [SubOp] [Data 0x01] ... CRC
    p = bytearray([0xAB, 0x00, 0x11, opcode, sub_op, 0x01])
    p.extend([0x00] * 13)
    p.append(sum(p) & 0xFF)
    return bytes(p)

async def strike(opcode, sub_op):
    try:
        async with BleakClient(MAC, timeout=5.0) as client:
            pkt = build_packet(opcode, sub_op)
            print(f"[!] Striking Pipeline: {opcode:02X} | {sub_op:02X}")
            await client.write_gatt_char(RX_WRITE, pkt, response=False)
            await asyncio.sleep(0.5)
    except Exception:
        pass

async def run():
    print("[+] Burst sequence initiated...")
    for op in MASTER_OPCODES:
        for sub in range(0x01, 0x05): # Testing first 4 sub-opcodes per pipeline
            await strike(op, sub)
            await asyncio.sleep(1.0) # Buffer recovery time
    print("[+] Burst sequence complete.")

if __name__ == "__main__":
    asyncio.run(run())

