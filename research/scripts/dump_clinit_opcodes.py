import os
import re

target_file = "target_dex/classes4.dex"
print(f"[*] Extracting Dalvik static initializer opcode assignments from {target_file}...\n")

# Target hardware symbols discovered in our previous extraction
targets = [
    b"DATA_TYPE_FIND_PHONE_OR_DEVICE",
    b"DATA_TYPE_MESSAGE_NOTICE",
    b"DATA_TYPE_MESSAGE_SWITCH",
    b"DATA_TYPE_CALL_REMIND"
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
                    
                print(f"[+] Found Anchor: {target.decode('ascii')} at offset {hex(idx)}")
                
                # In Dalvik bytecode, integer constants (const/4, const/16, bipush) are pushed 
                # within a 128-byte window around the string literal reference in <clinit>
                start = max(0, idx - 64)
                end = min(len(data), idx + len(target) + 80)
                chunk = data[start:end]
                
                print("    --- Surround Bytecode Dump (Hex & ASCII) ---")
                for i in range(0, len(chunk), 16):
                    line = chunk[i:i+16]
                    hex_str = " ".join(f"{b:02X}" for b in line)
                    ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in line)
                    print(f"    {hex_str:<48} | {ascii_str}")
                
                # Extract potential integer constants (small hex values commonly used for opcodes)
                # Looking for bytes immediately following string load opcodes
                print("    [*] Potential Opcode Bytes nearby: ", end="")
                for b in chunk:
                    if 0x01 <= b <= 0x20 and b != 0x0C: # Filtering out common framing bytes
                        print(f"0x{b:02X} ", end="")
                print("\n" + "-" * 65)
                idx += len(target)
else:
    print("[-] Could not locate classes4.dex. Ensure target_dex/ is unpacked.")
