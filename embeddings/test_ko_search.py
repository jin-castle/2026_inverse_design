import sys
sys.path.insert(0, '/mnt/c/Users/user/projects/meep-kb/query')
from semantic_search import semantic_search

print("=== 한국어 테스트 ===")
semantic_search("시뮬레이션이 발산해 NaN", kind="errors", n=3)

print("\n=== 한국어 adjoint ===")
semantic_search("adjoint 최적화 기울기 계산", kind="examples", n=3)
