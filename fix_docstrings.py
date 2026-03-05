import re

with open('insert_pipeline_patterns.py', 'r', encoding='utf-8') as f:
    content = f.read()

# code_snippet 내부 인라인 docstring을 # 주석으로 변환
# 패턴: 들여쓰기 + """...""" (한 줄짜리만)
content = re.sub(
    r'^(\s+)"""([^"]+)"""',
    lambda m: m.group(1) + '# ' + m.group(2).strip(),
    content,
    flags=re.MULTILINE
)

with open('insert_pipeline_patterns.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed inline docstrings.')

# 검증
import ast
try:
    ast.parse(content)
    print('Syntax OK')
except SyntaxError as e:
    print(f'Still error at line {e.lineno}: {e.msg}')
    lines = content.splitlines()
    for i in range(max(0, e.lineno-5), min(len(lines), e.lineno+3)):
        marker = '>>>' if i+1 == e.lineno else '   '
        print(f'{marker} {i+1}: {lines[i]}')
