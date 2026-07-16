import os
import re

target_dir = "target_dex"
print("[*] Scanning compiled Dalvik bytecode for exact payload assembly rules...\n")

keywords = [
    b"DATA_TYPE_USER_INFO",
    b"DATA_TYPE_UNIT_SETTING",
    b"DATA_TYPE_LANGUAGE_SETTING",
    b"DATA_TYPE_PAIR_FINISH",
    b"DATA_TYPE_APP_SYNC",
    b"DATA_TYPE_DEV_SYNC"
]

if os.path.exists(target_dir):
    for file in sorted(os.listdir(target_dir)):
        if file.endswith(".dex"):
            filepath = os.path.join(target_dir, file)
            with open(filepath, "rb") as f:
                content = f.read()
                
                for kw in keywords:
                    idx = 0
                    while True:
                        idx = content.find(kw, idx)
                        if idx == -1:
                            break
                            
                        print(f"[+] Found {kw.decode('ascii')} in {file} at offset {hex(idx)}")
                        
                        # Extract 256 bytes before and after to catch method names, error strings, and adjacent keys
                        start = max(0, idx - 128)
                        end = min(len(content), idx + 384)
                        chunk = content[start:end]
                        
                        # Find readable ASCII sequences in the surrounding code block
                        strings_found = re.findall(b'[a-zA-Z0-9_/$-]{4,50}', chunk)
                        clean_strings = [s.decode('ascii') for s in strings_found if not s.startswith(b'DATA_TYPE_')]
                        
                        # Deduplicate while preserving order
                        seen = set()
                        unique_strings = [x for x in clean_strings if not (x in seen or seen.add(x))]
                        
                        print("    Nearby Symbols & Methods:")
                        for s in unique_strings[:12]:
                            print(f"      -> {s}")
                        print("-" * 50)
                        idx += len(kw)
else:
    print("[-] target_dex directory not found. Please run from your watchenv root.")
