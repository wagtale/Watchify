import os

target_dir = "target_dex"
output_file = "packet_dump.txt"
header = b'\xab'

print(f"[*] Scanning for packet headers, writing to {output_file}...")
with open(output_file, "w") as out:
    for filename in os.listdir(target_dir):
        if filename.endswith(".dex"):
            path = os.path.join(target_dir, filename)
            with open(path, "rb") as f:
                data = f.read()
                offset = data.find(header)
                while offset != -1:
                    chunk = data[offset:offset+20]
                    if len(chunk) == 20:
                        out.write(f"Offset {hex(offset)}: {chunk.hex().upper()}\n")
                    offset = data.find(header, offset + 1)
print("[+] Scan complete. Check packet_dump.txt.")
