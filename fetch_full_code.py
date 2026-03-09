import urllib.request, json

# Fetch all examples
data = json.dumps({}).encode()
req = urllib.request.Request(
    "http://localhost:7860/api/examples/list",
    data=data,
    headers={"Content-Type": "application/json"},
    method='POST'
)
r = urllib.request.urlopen(req, timeout=30)
examples = json.loads(r.read())

# Build a dict by id
by_id = {ex['id']: ex for ex in examples}

# IDs we care about (fixable)
target_ids = [
    382, 563,  # np.complex_ fix
    364, 540,  # __file__ fix
    521,       # argparse fix
    332, 393, 502, 577,  # PyMieScatt - skip
    329, 499,  # gdspy - skip
    596,       # nlopt - skip
    269, 428, 569, 597, 598,  # syntax error (truncated)
    333, 410, 595,  # partial execution / timeout
    # Type C timeouts
    341, 353, 374, 378, 381, 389, 391, 400, 406,
    505, 513, 526, 528, 539, 548, 554, 559, 562, 573, 575, 591, 592,
]

result = {}
for id_ in target_ids:
    if id_ in by_id:
        result[id_] = {
            'id': id_,
            'title': by_id[id_]['title'],
            'code': by_id[id_]['code'],
            'status': by_id[id_]['result_status'],
        }
    else:
        result[id_] = {'id': id_, 'error': 'not found'}

with open('/tmp/full_codes.json', 'w') as f:
    json.dump(result, f, ensure_ascii=False)
print(f"Saved {len(result)} examples")
for id_ in target_ids:
    code = result.get(id_, {}).get('code', '')
    print(f"ID {id_}: {len(code)} chars")
