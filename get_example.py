import urllib.request, json, sys
ex_id = int(sys.argv[1])
# Try different endpoints
for url in [
    f"http://localhost:7860/api/examples/list",
    f"http://localhost:7860/api/examples/list?limit=5",
]:
    try:
        req = urllib.request.Request(url, method='GET')
        r = urllib.request.urlopen(req, timeout=10)
        data = json.loads(r.read())
        print(f"URL: {url}")
        print(f"Type: {type(data)}")
        if isinstance(data, list):
            print(f"Length: {len(data)}")
            if data:
                print(f"Keys: {list(data[0].keys())}")
        break
    except Exception as e:
        print(f"URL {url}: {e}")
