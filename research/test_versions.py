import urllib.request
import json

url = "https://wr.watchhealth.com.cn/app-halfwit/app-device/checkForUpdate"
headers = {
    "Content-Type": "application/json",
    "access-token": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJrZWl0aGJyb3dubGVlMjJAZ21haWwuY29tIiwicm9sZXMiOltdLCJ1c2VySWQiOjE4MTYwMDQxMzEwMjQ4MTkzMTAsInVzZXJuYW1lIjoia2VpdGhicm93bmxlZTIyQGdtYWlsLmNvbSIsImlhdCI6MTc4NDIxOTY1MywiZXhwIjoxNzg1NTE1NjUzfQ.-pK7pllog4YE_HDT5eAjbTQCXACnxACvscMVAYrSzZEdDT357-AinQZjqztvP2d_vZrQ5K7smotZwJ1cdmIhsA"
}

for hw in range(1, 10):
    for code in range(1, 5):
        fw = f"255.0{hw}.{code}.1.1"
        data = {
            "currentFirmware": fw,
            "language": "EN",
            "macAddress": "A1:B2:CC:09:78:0F",
            "watchId": "255"
        }
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            if res.get("data") and res["data"].get("updateFlag") == 1:
                print(f"Found update for {fw}: {res['data']}")
                exit(0)
print("No updates found in range")
