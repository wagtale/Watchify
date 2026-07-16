import os

target_dir = "target_dex"
print("[*] Scanning compiled dex blocks for raw protocol constants...")

for file in sorted(os.listdir(target_dir)):
    if file.endswith(".dex"):
        filepath = os.path.join(target_dir, file)
        with open(filepath, "rb") as f:
            data = f.read()
            
            # Look for the internal class path string in the data block
            idx = data.find(b"com/wtwd/utra/protocol/ProtocolUtils")
            if idx != -1:
                print(f"[+] Found ProtocolUtils logic structure inside: {file} at offset {hex(idx)}")
                
                # Scan the surrounding memory block for close-by hexadecimal markers or method structures
                start = max(0, idx - 1024)
                end = min(len(data), idx + 2048)
                surrounding_bytes = data[start:end]
                
                # Extract any clear ASCII patterns or structural identifiers
                words = []
                current_word = bytearray()
                for b in surrounding_bytes:
                    if 32 <= b <= 126:
                        current_word.append(b)
                    else:
                        if len(current_word) >= 3:
                            words.append(current_word.decode('ascii', errors='ignore'))
                        current_word = bytearray()
                        
                print(f"--- Extracted Variable Keys inside {file} ---")
                for w in sorted(list(set(words))):
                    if any(x in w.upper() for x in ["CMD", "KEY", "BLE", "SEND", "WRITE", "AUTH"]):
                        print(f"  Token: {w}")
