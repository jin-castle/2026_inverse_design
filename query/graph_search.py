#!/usr/bin/env python3
"""
MEEP-KB 그래프 검색 (NetworkX Knowledge Graph)

사용법:
  python query/graph_search.py "adjoint"               # 관련 노드 탐색
  python query/graph_search.py "EigenModeSource" --depth 2
  python query/graph_search.py "MPI" --traverse         # 전체 체인
  python query/graph_search.py --stats                  # 그래프 통계
  python query/graph_search.py --hubs                   # 핵심 허브 노드
"""

import argparse, pickle, sqlite3
from pathlib import Path
from collections import defaultdict

GRAPH_PATH = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge_graph.pkl")
DB_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")


def load_graph():
    if not GRAPH_PATH.exists():
        print("❌ 그래프 없음. `python graph/build_graph.py` 먼저 실행하세요.")
        return None
    import networkx as nx
    with open(GRAPH_PATH, "rb") as f:
        return pickle.load(f)


def find_nodes(G, query: str) -> list[str]:
    """쿼리와 라벨이 매칭되는 노드 목록"""
    q = query.lower()
    matched = []
    for nid, data in G.nodes(data=True):
        label = data.get("label", "").lower()
        ntype = data.get("type", "")
        if q in nid.lower() or q in label:
            matched.append((nid, ntype, data.get("label", nid)))
    return matched


def show_neighbors(G, nid: str, depth: int = 1, conn=None):
    import networkx as nx

    print(f"\n📍 노드: {nid}")
    data = G.nodes[nid]
    print(f"   유형: {data.get('type','?')} | {data.get('label','')[:80]}")
    if data.get('category'): print(f"   카테고리: {data['category']}")
    if data.get('url'):       print(f"   🔗 {data['url']}")
    if data.get('has_solution') is True: print("   ✅ 해결책 있음")

    # 엣지
    out_edges = list(G.out_edges(nid, data=True))
    in_edges  = list(G.in_edges(nid, data=True))

    # 관계별 그룹핑
    by_rel = defaultdict(list)
    for u, v, d in out_edges:
        target = v
        by_rel[d.get("rel","→")].append(target)
    for u, v, d in in_edges:
        source = u
        by_rel[f"←{d.get('rel','?')}"].append(source)

    print()
    for rel, targets in by_rel.items():
        # similar_error는 축약
        if rel == "similar_error":
            print(f"  [{rel}] {len(targets)}개 유사 에러")
            continue
        print(f"  [{rel}]")
        for t in targets[:8]:
            t_data = G.nodes.get(t, {})
            t_label = t_data.get("label", t)[:60]
            t_type  = t_data.get("type", "")
            print(f"    • [{t_type}] {t_label}")
        if len(targets) > 8:
            print(f"    ... 외 {len(targets)-8}개")


def traverse(G, start_nid: str, max_depth: int = 2):
    """BFS로 연결 그래프 탐색, 핵심 체인 출력"""
    import networkx as nx
    from collections import deque

    visited = set()
    queue   = deque([(start_nid, 0)])
    order   = []

    while queue:
        nid, depth = queue.popleft()
        if nid in visited or depth > max_depth:
            continue
        visited.add(nid)
        order.append((nid, depth))

        for _, neighbor, d in G.out_edges(nid, data=True):
            rel = d.get("rel", "")
            if rel == "similar_error":   # 노이즈 제거
                continue
            queue.append((neighbor, depth+1))

    print(f"\n🗺️  트래버설: {start_nid} (depth={max_depth})\n{'─'*55}")
    for nid, depth in order:
        data   = G.nodes.get(nid, {})
        label  = data.get("label", nid)[:60]
        ntype  = data.get("type", "?")
        indent = "  " * depth
        icon   = {"error":"🔴","concept":"🔵","api":"🟢","category":"🟡","example":"⚪"}.get(ntype,"•")
        print(f"{indent}{icon} [{ntype}] {label}")

    print(f"\n총 {len(order)}개 노드")


def stats(G):
    import networkx as nx
    print("\n📊 Knowledge Graph 통계")
    print("="*50)
    print(f"  노드 수: {G.number_of_nodes():,}")
    print(f"  엣지 수: {G.number_of_edges():,}")

    node_types = defaultdict(int)
    for n, d in G.nodes(data=True):
        node_types[d.get("type","?")] += 1
    print("\n  노드 유형별:")
    for t, cnt in sorted(node_types.items(), key=lambda x: -x[1]):
        print(f"    {t:<12}: {cnt:>5}개")

    edge_rels = defaultdict(int)
    for u, v, d in G.edges(data=True):
        edge_rels[d.get("rel","?")] += 1
    print("\n  엣지 관계별:")
    for r, cnt in sorted(edge_rels.items(), key=lambda x: -x[1]):
        print(f"    {r:<20}: {cnt:>5}개")


def hubs(G, top_n: int = 10):
    """가장 연결이 많은 허브 노드"""
    import networkx as nx
    degrees = [(nid, G.degree(nid), G.nodes[nid].get("label","")[:50],
                G.nodes[nid].get("type",""))
               for nid in G.nodes]
    degrees.sort(key=lambda x: -x[1])

    print(f"\n🌐 핵심 허브 노드 Top {top_n}")
    print("="*50)
    for nid, deg, label, ntype in degrees[:top_n]:
        icon = {"error":"🔴","concept":"🔵","api":"🟢","category":"🟡","example":"⚪"}.get(ntype,"•")
        print(f"  {icon} [{ntype:8}] degree={deg:3}  {label}")


def main():
    parser = argparse.ArgumentParser(description="MEEP-KB 그래프 검색")
    parser.add_argument("query", nargs="?", help="검색어 (개념/API/에러 이름)")
    parser.add_argument("--depth", type=int, default=1, help="이웃 탐색 깊이 (기본 1)")
    parser.add_argument("--traverse", action="store_true", help="BFS 트래버설 모드")
    parser.add_argument("--stats", action="store_true", help="그래프 통계")
    parser.add_argument("--hubs", action="store_true", help="허브 노드 목록")
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
        return

    print(f"🔍 '{args.query}' 매칭 노드: {len(matched)}개")
    for nid, ntype, label in matched[:3]:   # 상위 3개
        if args.traverse:
            traverse(G, nid, max_depth=args.depth)
        else:
            conn = sqlite3.connect(str(DB_PATH), timeout=30)
            show_neighbors(G, nid, depth=args.depth, conn=conn)
            conn.close()


if __name__ == "__main__":
    main()
