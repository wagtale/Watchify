import os
import re

target_file = "target_dex/classes4.dex"
print(f"[*] Extracting opcode assignments from {target_file}...\n")

# The critical hardware actuators discovered in your scan
targets = [
    b"DATA_TYPE_FIND_PHONE_OR_DEVICE",
    b"DATA_TYPE_MESSAGE_NOTICE",
    b"DATA_TYPE_MESSAGE_SWITCH",
    b"DATA_TYPE_CALL_REMIND",
    b"DATA_TYPE_SMS_REMIND"
]

if os.path.exists(target_file):
    with open(target_file, "rb") as f:
        data = f.read()
        
        for target in targets:
            idx = 0
            while True:
                idx = data.find(target, idx)
                if idx == -1:
                    break
                    
                print(f"[+] Found Anchor: {target.decode('ascii')}")
                
                # In Dalvik bytecode, integer definitions and enum constructors sit in the immediate vicinity
                # Let's inspect a 96-byte window around the string reference
                start = max(0, idx - 48)
                end = min(len(data), idx + len(target) + 48)
                chunk = data[start:end]
                
                # Format as hex dump paired with ASCII representation
                for i in range(0, len(chunk), 16):
                    line = chunk[i:i+16]
                    hex_str = " ".join(f"{b:02X}" for b in line)
                    ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in line)
                    print(f"    {hex_str:<48} | {ascii_str}")
                print("-" * 60)
                idx += len(target)
else:
    print("[-] Could not find classes4.dex in target_dex/.")
