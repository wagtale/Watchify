import urllib.request
import json
import sys

package = "com.wtwd.utrawatch"
# Using an open API endpoint that handles direct APK deliveries
url = f"https://api-apk.apps.evozi.com/apk/v1/dl?id={package}"

print(f"Requesting download link for {package}...")
req = urllib.request.Request(
    url, 
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)

try:
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode())
        if res.get("status") == "success":
            apk_url = res["url"]
            print("[+] Link acquired! Downloading clean binary...")
            
            # Pull down the real file data stream
            urllib.request.urlretrieve(apk_url, "utrawatch.apk")
            print("[+] Download complete: utrawatch.apk saved successfully.")
        else:
            print(f"[-] API Error: {res.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[-] Extraction failed: {e}")
