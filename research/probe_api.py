import urllib.request
import json

base_url = "https://wr.watchhealth.com.cn/app-halfwit/"
headers = {
    "Content-Type": "application/json",
    "access-token": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJrZWl0aGJyb3dubGVlMjJAZ21haWwuY29tIiwicm9sZXMiOltdLCJ1c2VySWQiOjE4MTYwMDQxMzEwMjQ4MTkzMTAsInVzZXJuYW1lIjoia2VpdGhicm93bmxlZTIyQGdtYWlsLmNvbSIsImlhdCI6MTc4NDIxOTY1MywiZXhwIjoxNzg1NTE1NjUzfQ.-pK7pllog4YE_HDT5eAjbTQCXACnxACvscMVAYrSzZEdDT357-AinQZjqztvP2d_vZrQ5K7smotZwJ1cdmIhsA"
}

def probe_get(endpoint):
    url = base_url + endpoint
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            print(f"[{endpoint}] GET OK: {json.dumps(res, ensure_ascii=False)}")
    except Exception as e:
        pass

probe_get("app-dial/getDialList?currentPage=1&pageSize=10&watchId=102")
probe_get("app-dial/getDefaultDialList?currentPage=1&pageSize=10&watchId=102")
