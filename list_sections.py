import json

with open(r'C:\Users\JHONATA\.local\share\opencode\tool-output\tool_e40885570001CgcjRrgBw6EIPH', 'r', encoding='utf-8') as f:
    d = json.load(f)

out = '\n'.join(d.get('outputStream', []))

# Parse the output into sections
sections = out.split('=== ')
for i, section in enumerate(sections):
    if not section.strip():
        continue
    # Get the header (first line)
    lines = section.split('\n')
    header = lines[0].strip().rstrip('= ').strip()
    print(f"SECTION {i}: {header}")
