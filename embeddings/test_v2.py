import sys
sys.path.insert(0, '/mnt/c/Users/user/projects/meep-kb/query')

print("=" * 60)
print("Part A: semantic_search_v2 한국어 테스트")
print("=" * 60)

from semantic_search_v2 import semantic_search

print("\n[1] '시뮬레이션이 발산해' → errors")
semantic_search("시뮬레이션이 발산해", kind="errors", n=3, verbose=True)

print("\n[2] '모드 소스 설정 방법' → docs")
semantic_search("모드 소스 설정 방법", kind="docs", n=3, verbose=True)

print("\n[3] '최적화 기울기 계산' → examples")
semantic_search("최적화 기울기 계산", kind="examples", n=3, verbose=True)
