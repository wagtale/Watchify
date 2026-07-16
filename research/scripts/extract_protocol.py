import urllib.request
import json
import zipfile
import re
import os

PACKAGE = "com.wtwd.utrawatch"
API_URL = f"https://api-apk.apps.evozi.com/apk/v1/dl?id={PACKAGE}"

print(f"[*] Fetching direct download mirror for {PACKAGE}...")
req = urllib.request.Request(API_URL, headers={'User-Agent': 'Mozilla/5.0'})

try:
    # 1. Download the clean binary archive
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode())
        if res.get("status") == "success":
            print("[+] Target acquired. Downloading uncorrupted APK...")
            urllib.request.urlretrieve(res["url"], "target.apk")
        else:
            print("[-] Mirror busy. Swapping to secondary direct fallback...")
            fallback = "https://d.apkpure.com/b/APK/com.wtwd.utrawatch?version=latest"
            req2 = urllib.request.Request(fallback, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req2) as dl:
                with open("target.apk", "wb") as w:
                    w.write(dl.read())

    # 2. Extract compiled dex blocks natively in Python
    print("[+] Extraction successful. Unzipping Android bytecode structures...")
    with zipfile.ZipFile("target.apk", "r") as z:
        for file in z.namelist():
            if file.startswith("classes") and file.endswith(".dex"):
                z.extract(file, "extracted_dex")
                print(f"  └── Extracted: {file}")

    print("\n[*] Scanning bytecode matrices for the BLE command dictionary...")
    
    # Hex patterns matching common Chinese wearable protocols (AB, DF, 55 AA)
    packet_pattern = re.compile(b'(CMD_|KEY_|WRITE_|BLE_)[A-Z0-9_]{2,20}')
    
    for root, dirs, files in os.walk("extracted_dex"):
        for file in files:
            with open(os.path.join(root, file), "rb") as f:
                content = f.read()
                
                # Extract all readable strings near the BLE protocol space
                matches = set(re.findall(b'[a-zA-Z0-9_]{4,30}', content))
                for match in matches:
                    decoded = match.decode('utf-8', errors='ignore')
                    if any(x in decoded.upper() for x in ["B002", "B001", "WTWD", "PROTOCOL", "COMMAND"]):
                        print(f" Found Structural Token: {decoded}")

    print("\n[+] Scan complete. Clean up temporary files...")
    os.system("rm -rf target.apk extracted_dex")

except Exception as e:
    print(f"[-] Automated capture paused: {e}")
    print("[!] Fallback: Let's create a direct protocol decoder based on your response stream.")
