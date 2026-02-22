#!/usr/bin/env python3
"""
MEEP-KB 그래프 검색 v2 — 개선 사항 (from review_20260222.md):
  - 양방향 트래버설 (concept/category 시작점에서도 탐색 가능)
  - 한국어 alias 노드 지원 (발산, 소스, 모드, 최적화 등)
  - show_neighbors() 미사용 파라미터 제거
  - v2 그래프(knowledge_graph_v2.pkl) 사용

사용법:
  python query/graph_search_v2.py "adjoint"
  python query/graph_search_v2.py "발산" --traverse
  python query/graph_search_v2.py "NaN" --depth 2
  python query/graph_search_v2.py "EigenModeSource" --depth 2
  python query/graph_search_v2.py --stats
  python query/graph_search_v2.py --hubs
"""

import argparse, pickle, sqlite3
from pathlib import Path
from collections import defaultdict

GRAPH_PATH = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge_graph_v2.pkl")
DB_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")


def load_graph():
    path = GRAPH_PATH
    if not path.exists():
        # fallback: v1
        path = Path(str(GRAPH_PATH).replace("_v2", ""))
        if not path.exists():
            print("❌ 그래프 없음. `python graph/build_graph_v2.py` 먼저 실행하세요.")
            return None
        print(f"⚠️  v2 없음, v1 로드: {path.name}")
    with open(path, "rb") as f:
        return pickle.load(f)


def find_nodes(G, query: str) -> list:
    """
    쿼리 매칭:
    1. 노드 ID / label 직접 매칭
    2. 한국어 alias 노드 경유 매칭 (ko: 접두사 포함)
    """
    q = query.lower()
    matched = []
    seen = set()

    for nid, data in G.nodes(data=True):
        label = data.get("label", "").lower()
        if q in nid.lower() or q in label:
            if nid not in seen:
                matched.append((nid, data.get("type",""), data.get("label", nid)))
                seen.add(nid)

    # 한국어 alias 노드를 통한 간접 매칭
    for nid, data in G.nodes(data=True):
        if data.get("type") == "alias_ko" and q in data.get("label","").lower():
            # alias_of 엣지로 연결된 영어 개념 노드 추가
            for _, target, d in G.out_edges(nid, data=True):
                if d.get("rel") == "alias_of" and target not in seen:
                    t_data = G.nodes.get(target, {})
                    matched.append((target, t_data.get("type",""), t_data.get("label", target)))
                    seen.add(target)

    return matched


def show_neighbors(G, nid: str):
    """노드 주변 엣지/이웃 요약 출력"""
    print(f"\n📍 노드: {nid}")
    data = G.nodes[nid]
    print(f"   유형: {data.get('type','?')} | {data.get('label','')[:80]}")
    if data.get('category'): print(f"   카테고리: {data['category']}")
    if data.get('url'):      print(f"   🔗 {data['url']}")
    if data.get('has_solution') is True: print("   ✅ 해결책 있음")

    by_rel = defaultdict(list)
    for u, v, d in G.out_edges(nid, data=True):
        by_rel[d.get("rel","→")].append(v)
    for u, v, d in G.in_edges(nid, data=True):
        by_rel[f"←{d.get('rel','?')}"].append(u)

    print()
    for rel, targets in sorted(by_rel.items()):
        if rel in ("similar_error", "←similar_error"):
            print(f"  [{rel}] {len(targets)}개")
            continue
        # mentioned_in / used_in 은 많을 수 있으니 요약
        if rel in ("mentioned_in", "←mentioned_in", "used_in", "←used_in"):
            print(f"  [{rel}] {len(targets)}개 (상위 5개만)")
            for t in targets[:5]:
                t_data = G.nodes.get(t, {})
                print(f"    • [{t_data.get('type','')}] {t_data.get('label', t)[:60]}")
            continue
        print(f"  [{rel}]")
        for t in targets[:8]:
            t_data = G.nodes.get(t, {})
            print(f"    • [{t_data.get('type','')}] {t_data.get('label', t)[:60]}")
        if len(targets) > 8:
            print(f"    ... 외 {len(targets)-8}개")


def traverse(G, start_nid: str, max_depth: int = 2):
    """
    v2: 양방향 BFS 트래버설
    - out_edges (순방향) + in_edges (역방향) 모두 탐색
    - similar_error / mentioned_in / used_in 제외 (노이즈 감소)
    """
    from collections import deque

    SKIP_RELS = {"similar_error", "mentioned_in", "used_in",
                 "←similar_error", "←mentioned_in", "←used_in"}

    visited = set()
    queue   = deque([(start_nid, 0, None)])   # (node, depth, rel_label)
    order   = []

    while queue:
        nid, depth, edge_label = queue.popleft()
        if nid in visited or depth > max_depth:
            continue
        visited.add(nid)
        order.append((nid, depth, edge_label))

        # 순방향
        for _, neighbor, d in G.out_edges(nid, data=True):
            rel = d.get("rel","")
            if rel not in SKIP_RELS:
                queue.append((neighbor, depth+1, f"→{rel}"))

        # 역방향 (v2 추가)
        for source, _, d in G.in_edges(nid, data=True):
            rel = d.get("rel","")
            if rel not in SKIP_RELS:
                queue.append((source, depth+1, f"←{rel}"))

    print(f"\n🗺️  트래버설 v2: {start_nid} (depth={max_depth}, 양방향)\n{'─'*55}")
    for nid, depth, edge_label in order:
        data   = G.nodes.get(nid, {})
        label  = data.get("label", nid)[:60]
        ntype  = data.get("type", "?")
        indent = "  " * depth
        icon   = {"error":"🔴","concept":"🔵","api":"🟢","category":"🟡",
                  "example":"⚪","alias_ko":"🇰🇷"}.get(ntype,"•")
        edge_str = f" [{edge_label}]" if edge_label else ""
        print(f"{indent}{icon} [{ntype}]{edge_str} {label}")

    print(f"\n총 {len(order)}개 노드 탐색")


def stats(G):
    print("\n📊 Knowledge Graph v2 통계")
    print("="*50)
    print(f"  노드 수: {G.number_of_nodes():,}")
    print(f"  엣지 수: {G.number_of_edges():,}")

    node_types = defaultdict(int)
    for n, d in G.nodes(data=True):
        node_types[d.get("type","?")] += 1
    print("\n  노드 유형별:")
    for t, cnt in sorted(node_types.items(), key=lambda x: -x[1]):
        print(f"    {t:<15}: {cnt:>5}개")

    edge_rels = defaultdict(int)
    for u, v, d in G.edges(data=True):
        edge_rels[d.get("rel","?")] += 1
    print("\n  엣지 관계별:")
    for r, cnt in sorted(edge_rels.items(), key=lambda x: -x[1]):
        print(f"    {r:<25}: {cnt:>5}개")


def hubs(G, top_n: int = 10):
    degrees = [(nid, G.degree(nid),
                G.nodes[nid].get("label","")[:50],
                G.nodes[nid].get("type",""))
               for nid in G.nodes]
    degrees.sort(key=lambda x: -x[1])
    print(f"\n🌐 핵심 허브 노드 Top {top_n}")
    print("="*50)
    for nid, deg, label, ntype in degrees[:top_n]:
        icon = {"error":"🔴","concept":"🔵","api":"🟢","category":"🟡",
                "example":"⚪","alias_ko":"🇰🇷"}.get(ntype,"•")
        print(f"  {icon} [{ntype:10}] degree={deg:3}  {label}")


def main():
    parser = argparse.ArgumentParser(description="MEEP-KB 그래프 검색 v2 (양방향 + 한국어)")
    parser.add_argument("query", nargs="?", help="검색어 (한국어 포함 가능)")
    parser.add_argument("--depth",    type=int, default=1)
    parser.add_argument("--traverse", action="store_true", help="BFS 트래버설 모드")
    parser.add_argument("--stats",    action="store_true")
    parser.add_argument("--hubs",     action="store_true")
    args = parser.parse_args()

    G = load_graph()
    if G is None:
        return

    if args.stats:
        stats(G)
        return
    if args.hubs:
        hubs(G)
        return
    if not args.query:
        parser.print_help()
        return

    matched = find_nodes(G, args.query)
    if not matched:
        print(f"❌ '{args.query}' 관련 노드 없음")
        # 한국어 alias 힌트
        print("💡 한국어 검색어 힌트: 발산, 소스, 모드, 플럭스, 최적화, 기울기, 병렬, 설치, 구조, 경계, 포토닉결정")
        return

    print(f"🔍 '{args.query}' 매칭 노드: {len(matched)}개")
    for nid, ntype, label in matched[:3]:
        if args.traverse:
            traverse(G, nid, max_depth=args.depth)
        else:
            show_neighbors(G, nid)


if __name__ == "__main__":
    main()
