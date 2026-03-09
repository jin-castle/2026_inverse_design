import urllib.request, json

r = urllib.request.urlopen("http://localhost:7860/openapi.json")
d = json.loads(r.read())

# Find the ingest/result endpoint
for path, methods in d.get('paths', {}).items():
    if 'ingest' in path or 'result' in path:
        print(f"Path: {path}")
        for method, spec in methods.items():
            print(f"  Method: {method}")
            body = spec.get('requestBody', {})
            if body:
                content = body.get('content', {})
                for ctype, cspec in content.items():
                    schema_ref = cspec.get('schema', {}).get('$ref', '')
                    schema_direct = cspec.get('schema', {})
                    print(f"  Content-Type: {ctype}")
                    if schema_ref:
                        # look up the schema
                        ref_name = schema_ref.split('/')[-1]
                        schema = d.get('components', {}).get('schemas', {}).get(ref_name, {})
                        print(f"  Schema ({ref_name}):", json.dumps(schema, indent=4)[:2000])
                    else:
                        print(f"  Schema:", json.dumps(schema_direct, indent=4)[:1000])
