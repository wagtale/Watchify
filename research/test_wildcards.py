import urllib.request
import json
import time

url = "https://wr.watchhealth.com.cn/app-halfwit/app-device/checkForUpdate"
headers = {
    "Content-Type": "application/json",
    "access-token": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJrZWl0aGJyb3dubGVlMjJAZ21haWwuY29tIiwicm9sZXMiOltdLCJ1c2VySWQiOjE4MTYwMDQxMzEwMjQ4MTkzMTAsInVzZXJuYW1lIjoia2VpdGhicm93bmxlZTIyQGdtYWlsLmNvbSIsImlhdCI6MTc4NDIxOTY1MywiZXhwIjoxNzg1NTE1NjUzfQ.-pK7pllog4YE_HDT5eAjbTQCXACnxACvscMVAYrSzZEdDT357-AinQZjqztvP2d_vZrQ5K7smotZwJ1cdmIhsA"
}

def check(fw, wid):
    data = {
        "currentFirmware": fw,
        "language": "EN",
        "macAddress": "A1:B2:CC:09:78:0F",
        "watchId": str(wid) if wid is not None else None
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            if res.get("data") and res["data"].get("updateFlag") == 1:
                print(f"SUCCESS! watchId={wid}, fw={fw} -> {res['data']}")
                return True
            elif res.get("code") == 4001:
                pass
            else:
                pass
    except Exception as e:
        pass
    return False

print("Starting full scan of watchId 0 to 500...")
for wid in range(0, 500):
    check("0.0.0.0.0", str(wid))
print("Finished testing watchIds.")
