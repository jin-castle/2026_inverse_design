#!/usr/bin/env python3
"""
Knowledge Graph v2 — 개선 사항 (from review_20260222.md):
  - 역방향 엣지 추가 (cat:X → error:Y has_error)
  - MEEP_CONCEPTS 보강: gradient, DFT, harminv, hdf5, Dispersive 등
  - 한국어 alias 노드 추가 (발산→diverge 매핑)
  - CATEGORY_CONCEPTS 재분류 (install 과다 분류 교정)
  - knowledge_graph_v2.pkl 로 저장 (기존 v1 미수정)
"""

import sqlite3, pickle
from pathlib import Path
from collections import defaultdict

DB_PATH     = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
GRAPH_PATH  = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge_graph_v2.pkl")

# ── MEEP 핵심 개념/API 사전 (v2 — 보강) ─────────────────────────────────────
MEEP_CONCEPTS = {
    # Sources
    "EigenModeSource": "api", "GaussianSource": "api", "ContinuousSource": "api",
    "CustomSource": "api",
    # Monitors / DFT
    "FluxRegion": "api", "get_eigenmode_coefficients": "api",
    "add_flux": "api", "add_mode_monitor": "api", "add_dft_fields": "api",
    "DFT": "concept", "harminv": "concept", "hdf5": "concept",
    # Geometry
    "Block": "api", "Cylinder": "api", "Prism": "api", "Sphere": "api",
    "GeometricObject": "api",
    # Simulation
    "Simulation": "api", "PML": "api", "run": "api", "fields": "api",
    "until_after_sources": "api", "at_every": "api",
    # Adjoint
    "mpa": "concept", "OptimizationProblem": "api", "adjoint": "concept",
    "autograd": "concept", "gradient": "concept",
    # Materials
    "Medium": "api", "LorentzianSusceptibility": "api",
    "Dispersive": "concept", "epsilon": "concept",
    # MPB
    "mpb": "concept", "ModeSolver": "api", "band_func": "api",
    # Issues
    "MPI": "concept", "parallel": "concept", "convergence": "concept",
    "diverge": "concept", "NaN": "concept", "Inf": "concept",
    "Courant": "concept", "resolution": "concept",
    "mode": "concept", "waveguide": "concept", "photonic crystal": "concept",
    "legume": "concept", "ceviche": "concept",
    "symmetry": "concept", "periodic": "concept",
}

# 카테고리 재분류 (install 과다 분류 교정)
CATEGORY_CONCEPTS = {
    "adjoint":     ["adjoint", "autograd", "OptimizationProblem", "gradient"],
    "mpi":         ["MPI", "parallel", "mpirun", "cores"],
    "convergence": ["diverge", "NaN", "Inf", "Courant", "resolution"],
    "geometry":    ["Block", "Cylinder", "Prism", "geometry", "overlap", "GeometricObject"],
    "source":      ["EigenModeSource", "GaussianSource", "ContinuousSource", "source", "mode"],
    "monitor":     ["FluxRegion", "add_flux", "DFT", "monitor", "harminv", "hdf5"],
    "install":     ["conda", "pip", "install", "import", "version", "package"],
    "legume":      ["legume", "gme", "GME", "photonic crystal", "legume-gme"],
    "mpb":         ["mpb", "ModeSolver", "MPB", "band_func"],
    "runtime":     ["runtime", "segfault", "crash", "memory", "Dispersive"],
    "cfwdm":       ["cfwdm", "mode converter", "PhC", "EFC", "demux"],
    "general":     [],
}

# 한국어 alias 매핑 (ko → 영어 concept key)
KO_ALIASES = {
    "발산":   "diverge",
    "수렴":   "convergence",
    "소스":   "EigenModeSource",
    "모드":   "mode",
    "플럭스":  "FluxRegion",
    "구조":   "Block",
    "경계":   "PML",
    "슬랩":   "waveguide",
    "최적화":  "adjoint",
    "기울기":  "gradient",
    "병렬":   "MPI",
    "설치":   "install",
    "포토닉결정": "photonic crystal",
}


def extract_concepts(text: str) -> list:
    if not text:
        return []
    found = []
    for term in MEEP_CONCEPTS:
        if term.lower() in text.lower():
            found.append(term)
    return found


def build_graph(conn):
    import networkx as nx
    G = nx.DiGraph()
    print("Knowledge Graph v2 구축 중...")

    # ── 1. 카테고리 노드 ─────────────────────────────────────────
    for cat in CATEGORY_CONCEPTS:
        G.add_node(f"cat:{cat}", type="category", label=cat)

    # ── 2. 개념/API 노드 ─────────────────────────────────────────
    for term, ntype in MEEP_CONCEPTS.items():
        G.add_node(f"concept:{term}", type=ntype, label=term)

    # ── 3. 한국어 alias 노드 + 연결 ──────────────────────────────
    for ko, en in KO_ALIASES.items():
        ko_nid = f"ko:{ko}"
        en_nid = f"concept:{en}"
        G.add_node(ko_nid, type="alias_ko", label=ko)
        if G.has_node(en_nid):
            G.add_edge(ko_nid, en_nid, rel="alias_of")
    print(f"  한국어 alias 노드: {len(KO_ALIASES)}개")

    # ── 4. 에러 노드 + 엣지 ──────────────────────────────────────
    errors = conn.execute(
        "SELECT id, error_msg, category, cause, solution, source_url FROM errors"
    ).fetchall()

    for eid, msg, cat, cause, sol, url in errors:
        nid = f"error:{eid}"
        G.add_node(nid, type="error", label=msg[:80],
                   category=cat or "", has_solution=bool(sol), url=url or "")

        # 양방향 엣지: error ↔ category
        if cat and f"cat:{cat}" in G:
            G.add_edge(nid, f"cat:{cat}", rel="belongs_to")
            G.add_edge(f"cat:{cat}", nid, rel="has_error")   # ✅ v2 추가: 역방향

        # 개념 추출 + 연결
        all_text = f"{msg} {cause or ''} {sol or ''}"
        for concept in extract_concepts(all_text):
            cid = f"concept:{concept}"
            G.add_edge(nid, cid, rel="mentions")
            G.add_edge(cid, nid, rel="mentioned_in")         # ✅ v2 추가: 역방향

    print(f"  에러 노드: {len(errors)}개")

    # ── 5. 코드 예제 노드 + 엣지 ─────────────────────────────────
    examples = conn.execute(
        "SELECT id, title, tags, source_repo, code FROM examples"
    ).fetchall()

    for xid, title, tags, repo, code in examples:
        nid = f"example:{xid}"
        G.add_node(nid, type="example", label=title[:80],
                   repo=repo or "", tags=tags or "")
        for concept in extract_concepts(f"{title} {tags or ''} {(code or '')[:500]}"):
            cid = f"concept:{concept}"
            G.add_edge(nid, cid, rel="uses")
            G.add_edge(cid, nid, rel="used_in")             # ✅ v2 추가: 역방향

    print(f"  예제 노드: {len(examples)}개")

    # ── 6. 유사 에러 엣지 (카테고리별, 10쌍 제한) ────────────────
    cat_errors = defaultdict(list)
    for eid, _, cat, _, _, _ in errors:
        if cat:
            cat_errors[cat].append(f"error:{eid}")

    sim_edges = 0
    for cat, nodes in cat_errors.items():
        for i in range(min(len(nodes), 10)):
            for j in range(i+1, min(len(nodes), 10)):
                G.add_edge(nodes[i], nodes[j], rel="similar_error")
                sim_edges += 1

    # ── 7. 카테고리-개념 엣지 ────────────────────────────────────
    for cat, terms in CATEGORY_CONCEPTS.items():
        for term in terms:
            cid = f"concept:{term}"
            if G.has_node(cid):
                G.add_edge(f"cat:{cat}", cid, rel="key_concept")

    # 통계
    node_types = defaultdict(int)
    for n, d in G.nodes(data=True):
        node_types[d.get("type","?")] += 1

    print(f"\n📊 그래프 v2 통계:")
    print(f"  노드: {G.number_of_nodes():,}개")
    print(f"  엣지: {G.number_of_edges():,}개")
    for t, cnt in sorted(node_types.items()):
        print(f"  └ {t:<12}: {cnt}개")

    return G


def main():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    G = build_graph(conn)
    conn.close()
    if G:
        with open(GRAPH_PATH, "wb") as f:
            pickle.dump(G, f)
        size_kb = GRAPH_PATH.stat().st_size / 1024
        print(f"\n✅ knowledge_graph_v2.pkl 저장 완료 ({size_kb:.0f} KB)")
        print(f"   v1과 비교: 역방향 엣지 + 한국어 alias + 보강 개념 추가")


if __name__ == "__main__":
    main()
