import os
import re

target_file = "target_dex/classes4.dex"
print(f"[*] Scanning data segments of {target_file} for layout arrays...")

if os.path.exists(target_file):
    with open(target_file, "rb") as f:
        data = f.read()
        
        # Search for occurrences of target data structures
        idx = data.find(b"DATA_TYPE_USER_INFO")
        if idx != -1:
            print(f"[+] Found DATA_TYPE_USER_INFO anchor at offset {hex(idx)}")
            # Dump the surrounding 512 bytes in hex/ascii format to view neighboring values
            start = max(0, idx - 128)
            end = min(len(data), idx + 256)
            chunk = data[start:end]
            
            print("\n--- Raw Byte Segments near User Constants ---")
            for i in range(0, len(chunk), 16):
                line = chunk[i:i+16]
                hex_str = " ".join(f"{b:02X}" for b in line)
                ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in line)
                print(f"{hex_str:<48} | {ascii_str}")
else:
    print("[-] Missing classes4.dex target.")
