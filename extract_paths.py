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

# Output all path sections in full
for key in results:
    if key.startswith('/'):
        print(f"\n\n{'='*80}")
        print(f"PATH: {key}")
        print(f"{'='*80}")
        print(results[key])
        print()
