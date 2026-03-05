import ast, re

with open('insert_pipeline_patterns.py', 'r', encoding='utf-8') as f:
    src = f.read()

# Find all triple-quote positions
positions = [(m.start(), m.group()) for m in re.finditer(r'"{3}', src)]
print(f'Total triple-quotes: {len(positions)} (should be even)')
lines = src.splitlines()
for pos, q in positions:
    lineno = src[:pos].count('\n') + 1
    print(f'  line {lineno}: {lines[lineno-1][:80]}')
