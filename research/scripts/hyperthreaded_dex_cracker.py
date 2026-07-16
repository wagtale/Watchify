import os
import mmap
import struct
import concurrent.futures
import time
from collections import Counter

TARGET_DIR = "target_dex"

def crack_dex_file(filepath):
    """Hyperthreaded worker: Scans for ALL constant assignments near strings."""
    results = {}
    try:
        with open(filepath, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            if mm[:3] != b"dex":
                return []
                
            # Scan for all ASCII strings (min length 10)
            # and check the surrounding 128 bytes for Dalvik const instructions
            data = mm[:]
            for i in range(len(data) - 4):
                # Look for potential ASCII strings
                if 0x41 <= data[i] <= 0x5A: # Start with A-Z
                    chunk = data[i:i+30]
                    if all(32 <= b <= 126 for b in chunk):
                        # Found a string, now look for const/4 (0x12) or const/16 (0x13)
                        # in the preceding 128 bytes
                        start = max(0, i - 128)
                        lookback = data[start:i]
                        
                        found_ops = []
                        for j in range(len(lookback) - 2):
                            if lookback[j] == 0x13: # const/16
                                val = struct.unpack("<h", lookback[j+2:j+4])[0]
                                if 0 < val <= 64: found_ops.append(val)
                            elif lookback[j] == 0x12: # const/4
                                val = (lookback[j+1] >> 4) & 0x0F
                                if 0 < val <= 15: found_ops.append(val)
                        
                        if found_ops:
                            s = chunk.decode(errors='ignore')
                            if s not in results: results[s] = Counter()
                            results[s].update(found_ops)
            mm.close()
    except Exception:
        pass
    return filepath, results

def main():
    print(f"[*] Booting Blind-Scan DEX Analyzer (Cores: {os.cpu_count()})...")
    dex_files = [os.path.join(TARGET_DIR, f) for f in os.listdir(TARGET_DIR) if f.endswith(".dex")]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(crack_dex_file, dex): dex for dex in dex_files}
        for future in concurrent.futures.as_completed(futures):
            filepath, hits = future.result()
            if hits:
                print(f"[+] Found assignments in {os.path.basename(filepath)}:")
                for string, counts in hits.items():
                    print(f"    {string[:30]:<30} -> Opcodes: {dict(counts)}")
                print("-" * 60)

if __name__ == "__main__":
    main()
