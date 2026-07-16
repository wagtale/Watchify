import os
import re

target_file = "target_dex/classes4.dex"
print(f"[*] Extracting structural class map from {target_file}...")

if os.path.exists(target_file):
    with open(target_file, "rb") as f:
        data = f.read()
        
        # Search for all strings embedded in the protocol enum workspace
        pattern = re.compile(b'[A-Z_]{3,30}')
        matches = pattern.findall(data)
        
        # Filter down specifically to protocol structural codes
        keywords = ["LOGIN", "BIND", "PAIR", "AUTH", "SET", "TIME", "SYNC", "USER", "REQ"]
        clean_tokens = set()
        
        for match in matches:
            decoded = match.decode('ascii', errors='ignore')
            if any(k in decoded for k in keywords):
                clean_tokens.add(decoded)
                
        print("\n--- Hardcoded Protocol Token Map ---")
        for token in sorted(list(clean_tokens)):
            print(f" Detected Command Key: {token}")
else:
    print("[-] Target dex file missing.")
