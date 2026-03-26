import re

with open('api/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find diagnose endpoint
idx = content.find("@app.post(\"/api/diagnose\")")
if idx == -1:
    idx = content.find("@app.get(\"/api/diagnose\")")
if idx == -1:
    # search broadly
    for line in content.split('\n'):
        if 'diagnose' in line and '@app' in line:
            print('Found:', line)

if idx != -1:
    print(content[idx:idx+5000])
else:
    print("Searching for async def diagnose:")
    idx2 = content.find("async def diagnose")
    if idx2 != -1:
        print(content[idx2:idx2+5000])
    else:
        print("Not found. Searching for sim_error_v2:")
        idx3 = content.find("sim_error_v2")
        if idx3 != -1:
            print(content[max(0,idx3-500):idx3+2000])
        else:
            print("sim_error_v2 not in main.py")
            # Show all route definitions
            for m in re.finditer(r'@app\.(post|get|put)\([^\)]+\)', content):
                print(m.group(0))
