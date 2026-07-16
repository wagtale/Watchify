import os
import re

target_dir = "target_dex"
print("[*] Hunting for compiled enum opcode integers in Dalvik method space...\n")

# Targets we need exact opcodes for
target_symbols = [
    b"DATA_TYPE_FIND_PHONE_OR_DEVICE",
    b"DATA_TYPE_MESSAGE_NOTICE",
    b"DATA_TYPE_CALL_REMIND",
    b"DATA_TYPE_SMS_REMIND",
    b"DATA_TYPE_VIBRATE",
    b"DATA_TYPE_FIND_DEV"
]

if os.path.exists(target_dir):
    for file in sorted(os.listdir(target_dir)):
        if not file.endswith(".dex"):
            continue
        filepath = os.path.join(target_dir, file)
        with open(filepath, "rb") as f:
            data = f.read()
            
            for sym in target_symbols:
                idx = 0
                while True:
                    idx = data.find(sym, idx)
                    if idx == -1:
                        break
                        
                    # Check if this occurrence is in the String Pool (usually preceded by its character length byte)
                    char_len = len(sym)
                    if idx > 0 and data[idx-1] == char_len:
                        # This is just the string pool definition! Let's search for where this string ID is USED in code.
                        pass
                    
                    # Let's inspect a 120-byte window around this reference for Dalvik integer push opcodes
                    # Dalvik 'const/4' is opcode 0x12, 'const/16' is 0x13, 'bipush' style pushes often use 0x12/0x13/0x14
                    start = max(0, idx - 60)
                    end = min(len(data), idx + char_len + 60)
                    chunk = data[start:end]
                    
                    # Look for sequence: [Small Int 0x00-0xFF] followed within 16 bytes by our symbol
                    print(f"[+] Match in {file} -> {sym.decode('ascii')}")
                    
                    # Extract readable bytecode hex patterns
                    hex_stream = " ".join(f"{b:02X}" for b in chunk)
                    print(f"    Raw Stream: ... {hex_stream[:80]} ...")                    
                    # Find integers that are likely Opcodes (1 to 50 decimal, not equal to the string length)
                    likely_opcodes = []
                    for b in chunk:
                        if 0x01 <= b <= 0x30 and b != char_len and b != 0x0C:
                            likely_opcodes.append(f"0x{b:02X} ({b})")
                            
                    # Remove duplicates while preserving order
                    seen = set()
                    clean_opcodes = [x for x in likely_opcodes if not (x in seen or seen.add(x))]
                    print(f"    [*] Candidate Sub-Opcodes: {', '.join(clean_opcodes[:8])}")
                    print("-" * 65)
                    
                    idx += len(sym)
else:
    print("[-] target_dex/ directory missing. Run from watchenv root.")
