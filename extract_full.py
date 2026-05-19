import json

with open(r'C:\Users\JHONATA\.local\share\opencode\tool-output\tool_e40885570001CgcjRrgBw6EIPH', 'r', encoding='utf-8') as f:
    d = json.load(f)

out = '\n'.join(d.get('outputStream', []))

# Parse the output into sections
sections = out.split('=== ')
results = {}

for section in sections:
    if not section.strip():
        continue
    lines = section.split('\n')
    header = lines[0].strip().rstrip('= ').strip()
    body = '\n'.join(lines[1:]).strip()
    results[header] = body

# Output all path sections (they start with /)
print("=" * 80)
print("PATH SECTIONS (containing 'message' or 'session'):")
print("=" * 80)
for key in results:
    if key.startswith('/'):
        print(f"\n\n{'='*60}")
        print(f"PATH: {key}")
        print(f"{'='*60}")
        print(results[key])

print("\n\n")
print("=" * 80)
print("SCHEMA SECTIONS (all component schemas with key fields):")
print("=" * 80)
for key in results:
    if key.startswith('Schema:'):
        name = key.replace('Schema:', '').strip()
        body = results[key]
        # Try to parse as JSON to extract key fields
        try:
            schema = json.loads(body)
            props = schema.get('properties', {})
            fields = list(props.keys())
            schema_type = schema.get('type', 'object')
            print(f"\n{name} (type: {schema_type}): {', '.join(fields[:30])}{'...' if len(fields) > 30 else ''}")
        except:
            print(f"\n{name}: {body[:200]}")
