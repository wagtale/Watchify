import struct

with open("/root/dev/dial.bin", "rb") as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
magic = data[0:2].decode('ascii')
version = struct.unpack('<H', data[2:4])[0]
print(f"Magic: {magic}")
print(f"Version: 0x{version:04X}")

# Scan for common image headers in the file (like PNG, JPG, or raw RGB565 chunks)
png_magic = b'\x89PNG\r\n\x1a\n'
jpg_magic = b'\xff\xd8\xff'

png_count = data.count(png_magic)
jpg_count = data.count(jpg_magic)
print(f"Embedded PNGs found: {png_count}")
print(f"Embedded JPGs found: {jpg_count}")

# Look for block pointers
pointer_area = data[0x20:0x80]
print("Pointer area:")
for i in range(0, len(pointer_area), 4):
    val = struct.unpack('<I', pointer_area[i:i+4])[0]
    if val > 0:
        print(f"Offset 0x{0x20+i:02X}: {val} (0x{val:08X})")
