#!/usr/bin/env python3
"""
MEEP-KB Knowledge Graph 구축
SQLite DB → NetworkX 그래프 → GraphML 파일 저장

노드 유형: error, concept, api, pattern
엣지 유형: caused_by, solved_by, related_to, uses_api, similar_error
"""

import sqlite3, re, json, pickle
from pathlib import Path
from collections import defaultdict

DB_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
GRAPH_PATH = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge_graph.pkl")

# ── MEEP 핵심 개념/API 사전 ──────────────────────────────────────────────────
MEEP_CONCEPTS = {
    # Sources
    "EigenModeSource": "api", "GaussianSource": "api", "ContinuousSource": "api",
    "CustomSource": "api",
    # Monitors
    "FluxRegion": "api", "get_eigenmode_coefficients": "api",
    "add_flux": "api", "add_mode_monitor": "api",
    # Geometry
    "Block": "api", "Cylinder": "api", "Prism": "api", "Sphere": "api",
    # Simulation
    "Simulation": "api", "PML": "api", "run": "api", "fields": "api",
    # Adjoint
    "mpa": "concept", "OptimizationProblem": "api", "adjoint": "concept",
    "autograd": "concept",
    # Materials
    "Medium": "api", "LorentzianSusceptibility": "api",
    # MPB
    "mpb": "concept", "ModeSolver": "api",
    # Issues
    "MPI": "concept", "parallel": "concept", "convergence": "concept",
    "diverge": "concept", "NaN": "concept", "Inf": "concept",
    "Courant": "concept", "resolution": "concept",
    "mode": "concept", "waveguide": "concept", "photonic crystal": "concept",
    "legume": "concept", "ceviche": "concept",
}

CATEGORY_CONCEPTS = {
    "adjoint":     ["adjoint", "autograd", "OptimizationProblem", "gradient"],
    "mpi":         ["MPI", "parallel", "mpirun", "cores"],
    "convergence": ["diverge", "NaN", "Inf", "Courant", "resolution"],
    "geometry":    ["Block", "Cylinder", "Prism", "geometry", "overlap"],
    "source":      ["EigenModeSource", "GaussianSource", "source", "mode"],
    "monitor":     ["FluxRegion", "add_flux", "DFT", "monitor"],
    "install":     ["conda", "pip", "install", "import", "version"],
    "legume":      ["legume", "gme", "GME", "photonic crystal", "legume-gme"],
    "mpb":         ["mpb", "ModeSolver", "MPB"],
    "runtime":     ["runtime", "segfault", "crash", "memory"],
    "cfwdm":       ["cfwdm", "mode converter", "PhC", "EFC", "demux"],
    "general":     [],
}


def extract_concepts(text: str) -> list[str]:
    """텍스트에서 MEEP 관련 개념/API 추출"""
    if not text:
        return []
    found = []
    for term in MEEP_CONCEPTS:
        if term.lower() in text.lower():
            found.append(term)
    return found


def build_graph(conn):
    try:
        import networkx as nx
    except ImportError:
        print("NetworkX 설치 필요: pip3 install networkx")
        return None

    G = nx.DiGraph()
    print("그래프 구축 시작...")

    # ── 1. 카테고리 노드 ─────────────────────────────────────────
    for cat in CATEGORY_CONCEPTS:
        G.add_node(f"cat:{cat}", type="category", label=cat)
    print(f"  카테고리 노드: {len(CATEGORY_CONCEPTS)}개")

    # ── 2. 개념/API 노드 ─────────────────────────────────────────
    for term, ntype in MEEP_CONCEPTS.items():
        G.add_node(f"concept:{term}", type=ntype, label=term)
    print(f"  개념/API 노드: {len(MEEP_CONCEPTS)}개")

    # ── 3. 에러 노드 + 엣지 ──────────────────────────────────────
    errors = conn.execute(
        "SELECT id, error_msg, category, cause, solution, source_url FROM errors"
    ).fetchall()

    err_count = 0
    for eid, msg, cat, cause, sol, url in errors:
        nid = f"error:{eid}"
        G.add_node(nid, type="error", label=msg[:80],
                   category=cat or "", has_solution=bool(sol),
                   url=url or "")

        # 카테고리 연결
        if cat and f"cat:{cat}" in G:
            G.add_edge(nid, f"cat:{cat}", rel="belongs_to")

        # 개념 추출 + 연결
        all_text = f"{msg} {cause or ''} {sol or ''}"
        for concept in extract_concepts(all_text):
            cid = f"concept:{concept}"
            G.add_edge(nid, cid, rel="mentions")

        err_count += 1

    print(f"  에러 노드: {err_count}개")

    # ── 4. 코드 예제 노드 + 엣지 ─────────────────────────────────
    examples = conn.execute(
        "SELECT id, title, tags, source_repo, code FROM examples"
    ).fetchall()

    ex_count = 0
    for xid, title, tags, repo, code in examples:
        nid = f"example:{xid}"
        G.add_node(nid, type="example", label=title[:80],
                   repo=repo or "", tags=tags or "")

        # 코드에서 API 추출
        for concept in extract_concepts(f"{title} {tags or ''} {(code or '')[:500]}"):
            cid = f"concept:{concept}"
            G.add_edge(nid, cid, rel="uses")

        ex_count += 1

    print(f"  예제 노드: {ex_count}개")

    # ── 5. 유사 에러 엣지 (같은 카테고리 에러끼리 클러스터) ─────────────
    cat_errors = defaultdict(list)
    for eid, _, cat, _, _, _ in errors:
        if cat:
            cat_errors[cat].append(f"error:{eid}")

    sim_edges = 0
    for cat, nodes in cat_errors.items():
        # 같은 카테고리 내 최대 10쌍만
        for i in range(min(len(nodes), 10)):
            for j in range(i+1, min(len(nodes), 10)):
                G.add_edge(nodes[i], nodes[j], rel="similar_error")
                sim_edges += 1

    print(f"  유사 에러 엣지: {sim_edges}개")

    # ── 6. 카테고리-개념 엣지 ────────────────────────────────────
    for cat, terms in CATEGORY_CONCEPTS.items():
        for term in terms:
            cid = f"concept:{term}"
            if G.has_node(cid):
                G.add_edge(f"cat:{cat}", cid, rel="key_concept")

    # 통계
    print(f"\n📊 그래프 통계:")
    print(f"  노드: {G.number_of_nodes():,}개")
    print(f"  엣지: {G.number_of_edges():,}개")

    node_types = defaultdict(int)
    for n, d in G.nodes(data=True):
        node_types[d.get("type","?")] += 1
    for t, cnt in sorted(node_types.items()):
        print(f"  └ {t:<12}: {cnt}개")

    return G


def save_graph(G):
    with open(GRAPH_PATH, "wb") as f:
        import pickle
        pickle.dump(G, f)
    print(f"\n✅ 그래프 저장: {GRAPH_PATH}")
    print(f"   크기: {GRAPH_PATH.stat().st_size / 1024:.0f} KB")


def main():
    import networkx as nx
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    G = build_graph(conn)
    conn.close()
    if G:
        save_graph(G)


if __name__ == "__main__":
    main()
