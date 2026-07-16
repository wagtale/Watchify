import os
import re

target_dir = "target_dex"
print("[*] Scanning compiled Dalvik bytecode for actuator opcodes and notification frameworks...\n")

# Targeted keywords for hardware triggers, notifications, and alerts
actuator_keywords = [
    "FIND", "VIBRATE", "REMIND", "NOTIFY", "SMS", "MSG", "MESSAGE", 
    "PUSH", "ALERT", "CALL", "PHONE", "WATCH", "DIAL", "MOTOR"
]

if os.path.exists(target_dir):
    for file in sorted(os.listdir(target_dir)):
        if file.endswith(".dex"):
            filepath = os.path.join(target_dir, file)
            with open(filepath, "rb") as f:
                content = f.read()
                
                # Extract all uppercase ASCII string constants with underscores (Enum / Constant style)
                matches = re.findall(b'[A-Z0-9_]{4,40}', content)
                
                found_tokens = set()
                for match in matches:
                    decoded = match.decode('ascii', errors='ignore')
                    # Filter for tokens that match protocol commands OR actuator concepts
                    if any(kw in decoded for kw in actuator_keywords) and ("TYPE" in decoded or "CMD" in decoded or "DATA" in decoded or "BLE" in decoded or "SET" in decoded or "REQ" in decoded):
                        found_tokens.add(decoded)
                        
                if found_tokens:
                    print(f"--- Hardware Control Symbols in {file} ---")
                    for token in sorted(list(found_tokens)):
                        print(f"  -> {token}")
                    print("-" * 55)
else:
    print("[-] target_dex directory not found. Make sure you are in the root workspace.")
