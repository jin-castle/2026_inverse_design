#!/usr/bin/env python3
"""
MEEP-KB Pattern Dictionary — 3탭 버전
GET /dict  →  Patterns | Examples | Errors 탭 HTML
"""
import sqlite3, json, html as html_mod
from pathlib import Path

DB_PATH = Path("/app/db/knowledge.db")

# ── Patterns 카테고리 분류 ───────────────────────────────────────────────────
CATEGORY_RULES = [
    ("파이프라인",        "🔗", ["pipeline_"]),
    ("Adjoint 최적화",   "⚙️", [
        "adjoint_", "AdamOptimizer", "MappedSpace", "WarmRestarter",
        "BacktrackingLine", "AdaptiveBeta", "MsoptBeta", "LinearBeta",
        "born_validity", "optimization_5stage",
    ]),
    ("필터 & 투영",       "🔧", [
        "apply_conic", "apply_tanh", "get_beta_schedule", "harmonic_erosion",
        "harmonic_dilation", "compute_binarization", "find_minimum_feature",
        "get_adaptive_eta", "get_eroded", "get_dilated",
    ]),
    ("DFT & 모드 분석",   "📐", [
        "dft_", "EigenModeSource_", "eigenmode_", "mode_decomposition",
        "mode_coefficients", "mode_coeff", "coupler_mode", "ring_mode",
        "compute_overlap", "verify_eigenmode", "plot_dft",
    ]),
    ("시각화 & 출력",     "📊", [
        "plot_", "save_", "create_field_animation", "meep_visualization",
        "plot_convergence", "plot_final", "output_directory", "history_json",
        "array_metadata", "get_point_field",
    ]),
    ("도파관 & 공진기",   "〰️", [
        "straight_waveguide", "bent_waveguide", "bend_flux",
        "waveguide_source", "waveguide_crossing", "ring_resonator",
        "directional_coupler",
    ]),
    ("MPB 밴드 계산",     "🎵", ["mpb_", "phc_"]),
    ("지오메트리 & 재료", "🧱", [
        "geometry_", "materials_library", "material_dispersion",
        "material_grid", "cylinder_cross", "user_defined_material",
    ]),
    ("광학 소자",         "🔬", [
        "binary_grating", "finite_grating", "polarization_grating",
        "grating2d", "metasurface", "near_to_far", "antenna_radiation",
        "angular_reflection", "reflectance_quartz", "faraday_rotation",
        "perturbation_theory", "third_harmonic", "holey_waveguide",
        "metal_cavity", "oblique_", "plane_wave", "gaussian_beam",
    ]),
    ("MPI & 시스템",      "🖥️", [
        "mpi_parallel", "setup_logging", "stop_when_fields", "solve_cw_steady",
    ]),
    ("MCTP & 프로젝트",   "🏗️", [
        "mctp_core", "sio2_substrate", "source_monitor_size",
        "eig_parity_2d", "adam_optimizer_topology", "design_length_sweep",
    ]),
]
OTHER_CATEGORY = ("기타", "📦", [])


def _classify(name: str) -> tuple:
    for cat_name, emoji, keywords in CATEGORY_RULES:
        for kw in keywords:
            if name.startswith(kw) or kw in name:
                return cat_name, emoji
    return OTHER_CATEGORY[0], OTHER_CATEGORY[1]


# ── DB 로드 헬퍼 ─────────────────────────────────────────────────────────────
def _load_patterns() -> list:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    rows = conn.execute(
        "SELECT id, pattern_name, description, code_snippet, use_case, url "
        "FROM patterns ORDER BY pattern_name"
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        cat, emoji = _classify(row[1])
        result.append({
            "id": row[0], "name": row[1], "desc": row[2] or "",
            "code": row[3] or "", "use_case": row[4] or "",
            "url": row[5] or "", "cat": cat, "emoji": emoji,
        })
    return result


def _load_examples() -> list:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    # 성공+이미지 있는 것 먼저, 나머지는 id DESC
    rows = conn.execute(
        "SELECT id, title, code, description, tags, source_repo, author, "
        "file_path, created_at, result_images, result_stdout, "
        "result_run_time, result_executed_at, result_status "
        "FROM examples "
        "ORDER BY CASE WHEN result_status='success' AND result_images IS NOT NULL AND result_images != '[]' THEN 0 ELSE 1 END, id DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        images = []
        try:
            if r[9]:
                images = json.loads(r[9])
        except Exception:
            pass
        result.append({
            "id": r[0], "title": r[1] or "(제목 없음)",
            "code": r[2] or "", "desc": r[3] or "",
            "tags": [t.strip() for t in (r[4] or "").split(",") if t.strip()],
            "source_repo": r[5] or "", "author": r[6] or "",
            "file_path": r[7] or "", "created_at": (r[8] or "")[:10],
            "result_images": images,
            "result_stdout": r[10] or "",
            "result_run_time": r[11],
            "result_executed_at": (r[12] or "")[:19],
            "result_status": r[13] or "pending",
        })
    return result


def _load_notebooks() -> list:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    rows = conn.execute(
        "SELECT id, title, filename, folder, source_url, tags, cells, "
        "cell_count, code_count, image_count, created_at, cells_ko "
        "FROM notebooks ORDER BY id"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        cells_en, cells_ko = [], []
        try:
            if r[6]:  cells_en = json.loads(r[6])
        except Exception: pass
        try:
            raw_ko = r[11] if len(r) > 11 else None
            if raw_ko: cells_ko = json.loads(raw_ko)
        except Exception: pass
        result.append({
            "id": r[0], "title": r[1], "filename": r[2] or "",
            "folder": r[3] or "", "source_url": r[4] or "",
            "tags": [t.strip() for t in (r[5] or "").split(",") if t.strip()],
            "cells_en": cells_en,
            "cells_ko": cells_ko,
            "has_ko": bool(cells_ko),
            "cell_count": r[7] or 0,
            "code_count": r[8] or 0, "image_count": r[9] or 0,
            "created_at": (r[10] or "")[:10],
        })
    return result


def _load_errors() -> list:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    rows = conn.execute(
        "SELECT id, error_msg, category, cause, solution, source_type, created_at "
        "FROM errors ORDER BY category, id"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r[0], "error_msg": r[1] or "",
            "category": r[2] or "runtime",
            "cause": r[3] or "", "solution": r[4] or "",
            "source_type": r[5] or "", "created_at": (r[6] or "")[:10],
        })
    return result


# ── HTML 생성 ─────────────────────────────────────────────────────────────────
def _e(s: str) -> str:
    """HTML escape"""
    return html_mod.escape(str(s))


def _status_badge(status: str) -> str:
    colors = {
        "success": "#22c55e", "failed": "#ef4444",
        "timeout": "#f59e0b", "skip": "#6b7280", "pending": "#3b82f6",
    }
    labels = {
        "success": "✅ 실행완료", "failed": "❌ 실패",
        "timeout": "⏱️ 타임아웃", "skip": "⏭️ 스킵", "pending": "⏳ 대기중",
    }
    c = colors.get(status, "#6b7280")
    l = labels.get(status, status)
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">{l}</span>'


def _build_patterns_html(patterns: list) -> str:
    from collections import defaultdict
    cats = defaultdict(list)
    for p in patterns:
        cats[p["cat"]].append(p)

    toc = ""
    body = ""
    for cat_name, items in cats.items():
        emoji = items[0]["emoji"]
        anchor = cat_name.replace(" ", "_")
        toc += f'<li><a href="#cat_{anchor}" class="toc-link">{emoji} {_e(cat_name)} <span class="badge">{len(items)}</span></a></li>\n'
        body += f'<section class="category-section" id="cat_{anchor}">\n'
        body += f'<h2 class="cat-header">{emoji} {_e(cat_name)} <span class="cat-count">({len(items)}개)</span></h2>\n'
        for p in items:
            aid = f"pat_{p['id']}"
            body += f'''<div class="entry pattern-entry" id="{aid}">
  <div class="entry-header">
    <span class="entry-name">🔷 {_e(p["name"])}</span>
    <div class="entry-meta">
      {('<a class="tag" href="' + _e(p["url"]) + '" target="_blank">📎 ref</a>') if p["url"] else ""}
    </div>
  </div>'''
            if p["desc"]:
                body += f'<p class="entry-desc">{_e(p["desc"])}</p>\n'
            if p["use_case"]:
                body += f'<p class="entry-use"><strong>사용 예:</strong> {_e(p["use_case"])}</p>\n'
            if p["code"]:
                body += f'''<details class="toggle-block">
  <summary>📄 코드 보기</summary>
  <div class="code-block">
    <div class="code-header"><span>Python</span>
      <button class="copy-btn" onclick="copyCode(this)">복사</button>
    </div>
    <pre class="language-python"><code>{_e(p["code"])}</code></pre>
  </div>
</details>\n'''
            body += '</div>\n'
        body += '</section>\n'
    return toc, body


def _build_examples_html(examples: list) -> str:
    # 모든 태그 수집
    all_tags = set()
    for ex in examples:
        all_tags.update(ex["tags"])
    all_tags = sorted(all_tags)

    # 상태별 카운트
    status_cnt = {}
    for ex in examples:
        s = ex["result_status"]
        status_cnt[s] = status_cnt.get(s, 0) + 1

    # 이미지 있는 예제 수
    n_with_img = sum(1 for ex in examples if ex["result_images"])

    # 태그 필터 버튼 — 이미지 있는 것만 기본 선택
    tag_btns = '<button class="tag-filter" onclick="filterExamples(this, \'all\')">전체 ({}개)</button>\n'.format(len(examples))
    tag_btns += '<button class="tag-filter active" onclick="filterExamples(this, \'__has_image__\')">🖼️ 이미지 있음 ({}개)</button>\n'.format(n_with_img)
    for t in all_tags:
        cnt = sum(1 for ex in examples if t in ex["tags"])
        tag_btns += f'<button class="tag-filter" onclick="filterExamples(this, \'{_e(t)}\')">{_e(t)} ({cnt})</button>\n'

    # 상태 요약
    status_summary = " · ".join(
        f'<span style="color:{"#22c55e" if s=="success" else "#3b82f6" if s=="pending" else "#ef4444"}">{s}: {c}</span>'
        for s, c in sorted(status_cnt.items())
    )

    body = f'''
<div class="tab-toolbar">
  <div class="tag-filter-bar">
    {tag_btns}
  </div>
  <div class="status-summary">실행 현황: {status_summary}</div>
</div>
<div id="examples-list">
'''
    for ex in examples:
        tags_str = " ".join(ex["tags"])
        tag_badges = "".join(f'<span class="tag">{_e(t)}</span>' for t in ex["tags"])
        status = ex["result_status"]
        badge = _status_badge(status)

        has_img_attr = "true" if ex["result_images"] else "false"
        body += f'<div class="entry example-entry" data-tags="{_e(tags_str)}" data-has-image="{has_img_attr}">\n'
        body += f'''  <div class="entry-header">
    <span class="entry-name">📓 {_e(ex["title"])}</span>
    <div class="entry-meta">{badge} {tag_badges}
      <span class="muted">#{ex["id"]}</span>
      <span class="muted">{_e(ex["created_at"])}</span>
    </div>
  </div>\n'''

        if ex["desc"]:
            body += f'  <p class="entry-desc">{_e(ex["desc"][:300])}{"..." if len(ex["desc"]) > 300 else ""}</p>\n'

        # 코드 토글
        if ex["code"]:
            body += f'''  <details class="toggle-block">
    <summary>📄 코드 보기 ({len(ex["code"])} chars)</summary>
    <div class="code-block">
      <div class="code-header"><span>Python · {_e(ex["source_repo"])}</span>
        <button class="copy-btn" onclick="copyCode(this)">복사</button>
      </div>
      <pre class="language-python"><code>{_e(ex["code"][:5000]) + (" # ... (truncated)" if len(ex["code"]) > 5000 else "")}</code></pre>
    </div>
  </details>\n'''

        # 실행 결과 토글
        has_result = status == "success" and (ex["result_images"] or ex["result_stdout"])
        if has_result:
            run_time = f'{ex["result_run_time"]:.1f}s' if ex["result_run_time"] else "?"
            body += f'''  <details class="toggle-block result-block">
    <summary>🖼️ 실행 결과 보기 <span class="muted">({_e(ex["result_executed_at"])} · {run_time})</span></summary>
    <div class="result-content">\n'''
            # 이미지
            for img_path in ex["result_images"]:
                fname = img_path.split("/")[-1]
                url = f"/static/results/{fname}"
                body += f'      <img class="result-img" src="{url}" alt="{_e(fname)}" loading="lazy">\n'
            # stdout
            if ex["result_stdout"]:
                body += f'      <details class="toggle-block"><summary>📋 stdout</summary>\n'
                body += f'        <pre class="stdout-box">{_e(ex["result_stdout"][:2000])}</pre>\n'
                body += f'      </details>\n'
            body += '    </div>\n  </details>\n'
        elif status == "pending":
            body += '  <div class="pending-note">⏳ 아직 실행되지 않았습니다 — run_examples.py 실행 후 표시됩니다</div>\n'
        elif status in ("failed", "timeout"):
            body += f'  <div class="failed-note">실행 {status}: stdout을 확인하세요</div>\n'
            if ex["result_stdout"]:
                body += f'  <details class="toggle-block"><summary>📋 오류 출력</summary><pre class="stdout-box">{_e(ex["result_stdout"][:1000])}</pre></details>\n'

        body += '</div>\n'

    body += '</div>\n'
    return body


def _render_cells(cells: list, lang: str) -> str:
    """셀 목록 → HTML (lang: 'en' or 'ko')"""
    html     = ''
    code_idx = 0
    for cell in cells:
        ctype   = cell.get("type", "code")
        source  = cell.get("source", "")
        outputs = cell.get("outputs", [])

        if ctype == "markdown":
            html += f'<div class="nb-cell nb-md lang-{lang}" data-md="{_e(source)}"></div>\n'

        elif ctype == "code":
            code_idx += 1
            out_html = ''
            for out in outputs:
                if out.get("kind") == "image":
                    img_name = out.get("img_name", "")
                    url      = f"/static/results/{img_name}"
                    out_html += f'<img class="nb-img" src="{url}" alt="{_e(img_name)}" loading="lazy">\n'
                elif out.get("kind") == "text":
                    text   = out.get("text", "")
                    is_err = out.get("is_error", False)
                    cls    = "nb-stderr" if is_err else "nb-stdout"
                    out_html += f'<pre class="{cls}">{_e(text[:3000])}</pre>\n'

            html += f'''<div class="nb-cell nb-code lang-both">
  <div class="nb-cell-header">
    <span class="nb-in-label">In [{code_idx}]:</span>
    <button class="copy-btn" onclick="copyCode(this)">복사</button>
  </div>
  <div class="code-block">
    <pre class="language-python"><code>{_e(source)}</code></pre>
  </div>'''
            if out_html:
                html += f'''
  <div class="nb-output">
    <span class="nb-out-label">Out [{code_idx}]:</span>
    <div class="nb-output-content">{out_html}</div>
  </div>'''
            html += '\n</div>\n'
    return html


def _build_notebooks_html(notebooks: list) -> str:
    """Jupyter notebook 스타일 뷰어 HTML 생성 (한/영 전환 지원)"""
    if not notebooks:
        return '<p style="color:var(--muted)">저장된 노트북이 없습니다.</p>'

    sidebar = ''
    panels  = ''

    # PART 구분 정의
    PART_LABELS = {
        1: ("PART 1", "역전파 솔버 이해"),
        2: ("PART 2", "벤드 역설계 — 기본 → 심화"),
        4: ("PART 3", "고급 소자"),
        7: ("PART 4", "고급 기법"),
    }

    for nb in notebooks:
        nb_id    = f"nb_{nb['id']}"
        is_first = nb['id'] == notebooks[0]['id']
        has_ko   = nb.get("has_ko", False)

        # PART 구분선 삽입
        if nb['id'] in PART_LABELS:
            p_num, p_desc = PART_LABELS[nb['id']]
            sidebar += f'<div class="nb-part-label">📂 {p_num} — {p_desc}</div>\n'

        ko_badge = '<span style="background:#16a34a;color:#fff;font-size:10px;padding:1px 5px;border-radius:8px;margin-left:4px">한글</span>' if has_ko else ''
        sidebar += f'''<div class="nb-tab {'active' if is_first else ''}"
  onclick="switchNb('{nb_id}', this)"
  data-nb="{nb_id}">
  <div class="nb-tab-title">{_e(nb['title'])}{ko_badge}</div>
  <div class="nb-tab-meta">{nb['cell_count']}셀 · 코드{nb['code_count']} · 이미지{nb['image_count']}</div>
</div>\n'''

        # 출처 표시
        gh_url      = _e(nb["source_url"]) if nb["source_url"] else "#"
        source_html = f'''<div class="nb-source-credit">
  📌 출처: <a href="{gh_url}" target="_blank">NanoComp/meep GitHub</a>
  &nbsp;·&nbsp; <span style="color:var(--muted)">{_e(nb["filename"])}</span>
  &nbsp;·&nbsp; 코드 © MEEP Contributors (MIT License)
  {('<br><span style="color:#6b7280;font-size:11px">한국어 해설: meep-kb (연구 참고용 재서술, 원문 번역 아님)</span>' if has_ko else '')}
</div>'''

        # 영어 셀
        en_html = _render_cells(nb["cells_en"], "en")
        # 한국어 셀 (없으면 영어와 동일)
        ko_cells = nb["cells_ko"] if has_ko else nb["cells_en"]
        ko_html  = _render_cells(ko_cells, "ko")

        # 한/영 전환 버튼
        lang_btn = f'''<div class="lang-switcher">
  <button class="lang-btn {'active' if has_ko else ''}" onclick="setLang('{nb_id}','ko')" id="{nb_id}-btn-ko">🇰🇷 한국어</button>
  <button class="lang-btn {'active' if not has_ko else ''}" onclick="setLang('{nb_id}','en')" id="{nb_id}-btn-en">🇺🇸 English</button>
  {('' if has_ko else '<span class="muted" style="font-size:11px">한국어 해설 준비 중</span>')}
</div>'''

        tag_html = "".join(f'<span class="tag">{_e(t)}</span>' for t in nb["tags"])

        panels += f'''<div id="{nb_id}" class="nb-panel {'active' if is_first else ''}" data-lang="{'ko' if has_ko else 'en'}">
  <div class="nb-header">
    <h2>{_e(nb['title'])}</h2>
    <div class="nb-header-meta">{tag_html}</div>
    {source_html}
    {lang_btn}
  </div>
  <div class="nb-cells">
    <div class="nb-lang-wrap lang-ko-wrap">{ko_html}</div>
    <div class="nb-lang-wrap lang-en-wrap" style="display:none">{en_html}</div>
  </div>
</div>\n'''

    return f'''<div class="nb-layout">
  <nav class="nb-sidebar">
    <div class="nb-sidebar-title">📚 Notebooks ({len(notebooks)}개)</div>
    {sidebar}
  </nav>
  <div class="nb-main" id="nb-main">
    {panels}
  </div>
</div>'''


def _build_errors_html(errors: list) -> str:
    from collections import defaultdict
    cats = defaultdict(list)
    for e in errors:
        cats[e["category"]].append(e)

    body = f'<div class="error-stats">총 {len(errors)}개 에러 패턴 | 카테고리: {len(cats)}개</div>\n'

    cat_emojis = {
        "runtime": "🔴", "setup": "🟡", "geometry": "🔵",
        "adjoint": "⚙️", "mpi": "🖥️", "output": "📊",
    }
    for cat_name, items in sorted(cats.items()):
        emoji = cat_emojis.get(cat_name, "❌")
        body += f'<section class="category-section">\n'
        body += f'<h2 class="cat-header">{emoji} {_e(cat_name)} <span class="cat-count">({len(items)}개)</span></h2>\n'
        for e in items:
            body += f'<div class="entry">\n'
            body += f'  <div class="entry-header"><span class="entry-name error-msg">⚠️ {_e(e["error_msg"][:120])}</span></div>\n'
            if e["cause"]:
                body += f'  <p class="entry-desc"><strong>원인:</strong> {_e(e["cause"][:200])}</p>\n'
            body += f'  <details class="toggle-block"><summary>✅ 해결 방법</summary>\n'
            body += f'    <div class="solution-box">{_e(e["solution"])}</div>\n'
            body += f'  </details>\n</div>\n'
        body += '</section>\n'
    return body


# ── 메인 HTML 생성 ─────────────────────────────────────────────────────────────
def generate_html() -> str:
    patterns  = _load_patterns()
    examples  = _load_examples()
    errors    = _load_errors()
    notebooks = _load_notebooks()

    pat_toc, pat_body = _build_patterns_html(patterns)
    ex_body   = _build_examples_html(examples)
    err_body  = _build_errors_html(errors)
    nb_body   = _build_notebooks_html(notebooks)

    n_success = sum(1 for e in examples if e["result_status"] == "success")
    n_nb_imgs = sum(nb["image_count"] for nb in notebooks)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MEEP-KB Dictionary</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
<style>
:root {{
  --bg: #0f1117; --surface: #1a1d27; --border: #2d3144;
  --text: #e2e8f0; --muted: #6b7280; --accent: #6366f1;
  --accent2: #22c55e; --accent3: #f59e0b;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif;
       display: flex; flex-direction: column; min-height: 100vh; }}

/* ── 상단 헤더 ── */
#topbar {{
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 12px 24px; display: flex; align-items: center; gap: 16px;
  position: sticky; top: 0; z-index: 100;
}}
#topbar h1 {{ font-size: 18px; color: var(--accent); white-space: nowrap; }}
#topbar .stats {{ font-size: 13px; color: var(--muted); }}
#search-global {{ flex: 1; max-width: 360px; background: var(--bg);
  border: 1px solid var(--border); color: var(--text); border-radius: 8px;
  padding: 6px 12px; font-size: 13px; }}

/* ── 탭 네비게이션 ── */
#tab-nav {{
  background: var(--surface); border-bottom: 2px solid var(--border);
  padding: 0 24px; display: flex; gap: 0;
}}
.tab-btn {{
  background: none; border: none; color: var(--muted); cursor: pointer;
  padding: 14px 24px; font-size: 14px; font-weight: 600;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  transition: all 0.2s;
}}
.tab-btn:hover {{ color: var(--text); }}
.tab-btn.active {{ color: var(--accent); border-bottom-color: var(--accent); }}

/* ── 탭 컨텐츠 ── */
.tab-pane {{ display: none; }}
.tab-pane.active {{ display: flex; min-height: calc(100vh - 110px); }}

/* ── 사이드바 (Patterns 탭) ── */
#sidebar {{
  width: 260px; min-width: 220px; background: var(--surface);
  border-right: 1px solid var(--border); padding: 16px 12px;
  overflow-y: auto; position: sticky; top: 110px; height: calc(100vh - 110px);
  flex-shrink: 0;
}}
#sidebar input {{
  width: 100%; background: var(--bg); border: 1px solid var(--border);
  color: var(--text); border-radius: 6px; padding: 6px 10px; font-size: 12px; margin-bottom: 10px;
}}
.toc-link {{
  display: flex; justify-content: space-between; padding: 5px 8px;
  color: var(--muted); text-decoration: none; border-radius: 5px; font-size: 13px;
}}
.toc-link:hover {{ background: var(--border); color: var(--text); }}
.badge {{
  background: var(--border); color: var(--muted);
  padding: 1px 6px; border-radius: 10px; font-size: 11px;
}}

/* ── 메인 콘텐츠 ── */
#main-content {{ flex: 1; padding: 24px; overflow-y: auto; max-width: 1100px; }}
#main-content.full {{ max-width: 100%; }}

/* ── 카테고리 섹션 ── */
.cat-header {{
  font-size: 16px; padding: 10px 0 6px; margin-top: 28px; margin-bottom: 12px;
  border-bottom: 1px solid var(--border); color: var(--accent);
}}
.cat-count {{ font-size: 13px; color: var(--muted); font-weight: 400; }}

/* ── 엔트리 카드 ── */
.entry {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px; margin-bottom: 10px;
}}
.entry-header {{
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 6px;
}}
.entry-name {{ font-size: 14px; font-weight: 600; flex: 1; }}
.entry-meta {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 12px; }}
.entry-desc {{ font-size: 13px; color: var(--muted); margin: 4px 0 8px; line-height: 1.5; }}
.entry-use  {{ font-size: 12px; color: #94a3b8; margin-bottom: 8px; }}
.error-msg  {{ color: #fca5a5; font-size: 13px; }}

/* ── 태그 ── */
.tag {{
  background: #1e293b; color: #94a3b8; border: 1px solid var(--border);
  padding: 2px 8px; border-radius: 12px; font-size: 11px;
  text-decoration: none;
}}
.muted {{ color: var(--muted); font-size: 12px; }}

/* ── 토글 (details/summary) ── */
.toggle-block {{ margin-top: 8px; }}
.toggle-block > summary {{
  cursor: pointer; font-size: 13px; color: var(--accent); padding: 4px 0;
  list-style: none; display: flex; align-items: center; gap: 6px;
  user-select: none;
}}
.toggle-block > summary::-webkit-details-marker {{ display: none; }}
.toggle-block > summary::before {{ content: "▶"; font-size: 10px; transition: transform 0.2s; }}
.toggle-block[open] > summary::before {{ transform: rotate(90deg); }}

/* ── 소스 비교 토글 (노트북 안에서 사용) ── */
.src-toggle {{
  margin: 16px 0; background: #0d1a2b;
  border: 1px solid #1e3a5f; border-radius: 10px;
  padding: 4px 16px 12px;
}}
.src-toggle > summary {{
  cursor: pointer; padding: 12px 4px;
  color: #60a5fa; font-size: 14px; font-weight: 600;
  list-style: none; user-select: none;
}}
.src-toggle > summary::-webkit-details-marker {{ display: none; }}
.src-toggle[open] > summary span {{ visibility: hidden; }}
.src-toggle table {{
  width: 100%; border-collapse: collapse; font-size: 13px; margin: 12px 0;
}}
.src-toggle table th, .src-toggle table td {{
  border: 1px solid #1e3a5f; padding: 6px 10px; text-align: left;
}}
.src-toggle table th {{ background: #1e3a5f; color: #93c5fd; }}
.src-toggle img {{ max-width: 100%; border-radius: 8px; margin: 10px 0; display: block; }}
.src-toggle pre {{ background: #0f1525; border-radius: 6px; padding: 10px; overflow-x: auto; }}

/* ── 코드 블록 ── */
.code-block {{ border-radius: 8px; overflow: hidden; margin-top: 8px; }}
.code-header {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 12px; background: #1e1e1e; color: #aaa; font-size: 12px;
}}
.copy-btn {{
  background: #444; color: #ccc; border: none; padding: 2px 10px;
  border-radius: 4px; cursor: pointer; font-size: 11px;
}}
.copy-btn:hover {{ background: #555; color: #fff; }}
pre[class*="language-"] {{
  margin: 0 !important; padding: 14px !important;
  max-height: 420px; overflow-y: auto; font-size: 12px !important;
}}

/* ── 실행 결과 ── */
.result-content {{ padding: 12px; background: #0a0f1a; border-radius: 8px; margin-top: 8px; }}
.result-img {{
  max-width: 100%; border-radius: 8px; margin: 8px 0;
  border: 1px solid var(--border); display: block;
}}
.stdout-box {{
  background: #0d1117; color: #7dd3fc; padding: 10px 14px;
  border-radius: 6px; font-size: 12px; overflow-x: auto; white-space: pre-wrap;
  margin-top: 8px; max-height: 300px; overflow-y: auto;
}}
.solution-box {{
  background: #0d2818; color: #86efac; padding: 10px 14px;
  border-radius: 6px; font-size: 13px; margin-top: 6px; white-space: pre-wrap;
}}
.pending-note {{ color: #60a5fa; font-size: 12px; margin-top: 6px; padding: 4px 8px;
  background: #1e3a5f; border-radius: 6px; }}
.failed-note  {{ color: #f87171; font-size: 12px; margin-top: 6px; padding: 4px 8px;
  background: #3f0f0f; border-radius: 6px; }}

/* ── Examples 탭 툴바 ── */
.tab-toolbar {{ margin-bottom: 16px; }}
.tag-filter-bar {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
.tag-filter {{
  background: var(--surface); border: 1px solid var(--border); color: var(--muted);
  padding: 4px 12px; border-radius: 16px; cursor: pointer; font-size: 12px;
  transition: all 0.15s;
}}
.tag-filter:hover {{ border-color: var(--accent); color: var(--accent); }}
.tag-filter.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
.status-summary {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}

/* ── 에러 탭 ── */
.error-stats {{ font-size: 13px; color: var(--muted); margin-bottom: 16px; }}

/* ── 숨김 ── */
.example-entry.hidden {{ display: none; }}
.category-section.all-hidden {{ display: none; }}
.pattern-entry.hidden {{ display: none; }}

/* ── Notebooks 탭 ── */
.nb-layout {{
  display: flex; width: 100%; min-height: calc(100vh - 110px);
}}
.nb-sidebar {{
  width: 240px; min-width: 200px; background: var(--surface);
  border-right: 1px solid var(--border); padding: 12px 8px;
  overflow-y: auto; flex-shrink: 0;
  position: sticky; top: 110px; height: calc(100vh - 110px);
}}
.nb-sidebar-title {{
  font-size: 11px; color: var(--muted); padding: 4px 8px 10px;
  text-transform: uppercase; letter-spacing: 0.5px;
}}
.nb-part-label {{
  font-size: 10px; color: #4ade80; padding: 14px 8px 4px 8px;
  text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700;
  border-top: 1px solid #1e293b; margin-top: 6px;
}}
.nb-tab {{
  padding: 10px 12px; border-radius: 8px; cursor: pointer;
  margin-bottom: 4px; border: 1px solid transparent;
  transition: all 0.15s;
}}
.nb-tab:hover {{ background: var(--border); }}
.nb-tab.active {{ background: #1e293b; border-color: var(--accent); }}
.nb-tab-title {{ font-size: 13px; font-weight: 600; color: var(--text); line-height: 1.4; }}
.nb-tab-meta  {{ font-size: 11px; color: var(--muted); margin-top: 3px; }}

.nb-main {{ flex: 1; overflow-y: auto; padding: 24px 32px; max-width: 900px; }}
.nb-panel {{ display: none; }}
.nb-panel.active {{ display: block; }}

.nb-header {{ margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }}
.nb-header h2 {{ font-size: 20px; margin-bottom: 8px; }}
.nb-header-meta {{ display: flex; flex-wrap: wrap; gap: 6px; }}

/* ── 셀 ── */
.nb-cells {{ display: flex; flex-direction: column; gap: 4px; }}
.nb-cell {{ position: relative; }}

/* Markdown cell */
.nb-md {{ padding: 8px 0 16px; line-height: 1.8; }}
.nb-md-content h1,.nb-md-content h2,.nb-md-content h3 {{
  color: var(--accent); margin: 16px 0 8px; }}
.nb-md-content h1 {{ font-size: 22px; }}
.nb-md-content h2 {{ font-size: 18px; }}
.nb-md-content h3 {{ font-size: 15px; }}
.nb-md-content p  {{ color: var(--text); margin: 6px 0; }}
.nb-md-content ul, .nb-md-content ol {{ padding-left: 20px; }}
.nb-md-content li {{ margin: 4px 0; color: var(--text); }}
.nb-md-content code {{
  background: #1e293b; color: #7dd3fc;
  padding: 2px 6px; border-radius: 4px; font-size: 12px;
}}
.nb-md-content pre {{
  background: #0d1117; color: #e2e8f0; padding: 12px;
  border-radius: 8px; overflow-x: auto; margin: 10px 0;
}}
.nb-md-content blockquote {{
  border-left: 3px solid var(--accent); padding-left: 12px;
  color: var(--muted); margin: 8px 0;
}}
.nb-md-content table {{
  border-collapse: collapse; width: 100%; margin: 10px 0;
}}
.nb-md-content th, .nb-md-content td {{
  border: 1px solid var(--border); padding: 6px 10px; font-size: 13px;
}}
.nb-md-content th {{ background: var(--surface); color: var(--accent); }}

/* Code cell */
.nb-code {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; overflow: hidden; margin: 4px 0;
}}
.nb-cell-header {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 4px 12px; background: #12151f;
  border-bottom: 1px solid var(--border);
}}
.nb-in-label  {{ font-size: 11px; color: #6366f1; font-family: monospace; }}
.nb-out-label {{ font-size: 11px; color: #22c55e; font-family: monospace; }}

/* Output */
.nb-output {{
  border-top: 1px solid var(--border); padding: 12px 16px;
  background: #0a0d16;
}}
.nb-output-content {{ margin-top: 6px; }}
.nb-img {{
  max-width: 100%; border-radius: 6px; display: block;
  margin: 8px 0; border: 1px solid var(--border);
}}
.nb-stdout {{
  background: #0d1117; color: #d1fae5; padding: 8px 12px;
  border-radius: 6px; font-size: 12px; white-space: pre-wrap;
  max-height: 250px; overflow-y: auto; margin: 4px 0;
}}
.nb-stderr {{
  background: #1a0000; color: #fca5a5; padding: 8px 12px;
  border-radius: 6px; font-size: 12px; white-space: pre-wrap;
  max-height: 200px; overflow-y: auto; margin: 4px 0;
}}

/* ── 출처 표시 ── */
.nb-source-credit {{
  font-size: 12px; color: var(--muted); padding: 8px 12px;
  background: #0d1525; border-radius: 6px; margin: 8px 0;
  border-left: 3px solid #334155;
  line-height: 1.7;
}}
.nb-source-credit a {{ color: #60a5fa; text-decoration: none; }}
.nb-source-credit a:hover {{ text-decoration: underline; }}

/* ── 한/영 전환 버튼 ── */
.lang-switcher {{
  display: flex; align-items: center; gap: 8px; margin: 10px 0;
}}
.lang-btn {{
  background: var(--surface); border: 1px solid var(--border);
  color: var(--muted); padding: 5px 14px; border-radius: 16px;
  cursor: pointer; font-size: 13px; font-weight: 600;
  transition: all 0.15s;
}}
.lang-btn:hover  {{ border-color: var(--accent); color: var(--accent); }}
.lang-btn.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}

@media (max-width: 768px) {{
  #sidebar {{ display: none; }}
  .tab-btn {{ padding: 10px 12px; font-size: 12px; }}
  .nb-sidebar {{ display: none; }}
}}
</style>
</head>
<body>

<div id="topbar">
  <h1>🧠 MEEP-KB Dictionary</h1>
  <input id="search-global" type="text" placeholder="전체 검색..."
         oninput="globalSearch(this.value)">
  <div class="stats">
    Patterns: {len(patterns)} &nbsp;|&nbsp;
    Notebooks: {len(notebooks)} ({n_nb_imgs} 이미지) &nbsp;|&nbsp;
    Examples: {len(examples)} ({n_success} 실행완료) &nbsp;|&nbsp;
    Errors: {len(errors)}
  </div>
</div>

<div id="tab-nav">
  <button class="tab-btn active" onclick="switchTab('patterns', this)">⚙️ Patterns ({len(patterns)})</button>
  <button class="tab-btn" onclick="switchTab('notebooks', this)">📓 Notebooks ({len(notebooks)})</button>
  <button class="tab-btn" onclick="switchTab('examples', this)">📚 Examples ({len(examples)})</button>
  <button class="tab-btn" onclick="switchTab('errors', this)">❌ Errors ({len(errors)})</button>
</div>

<!-- ── Patterns 탭 ── -->
<div id="tab-patterns" class="tab-pane active">
  <nav id="sidebar">
    <input type="text" placeholder="패턴 검색..."
           oninput="filterPatterns(this.value)">
    <ul style="list-style:none; padding:0;">
      {pat_toc}
    </ul>
  </nav>
  <div id="main-content">
    {pat_body}
  </div>
</div>

<!-- ── Notebooks 탭 ── -->
<div id="tab-notebooks" class="tab-pane">
  <div style="width:100%">
    {nb_body}
  </div>
</div>

<!-- ── Examples 탭 ── -->
<div id="tab-examples" class="tab-pane">
  <div id="main-content" class="full" style="padding:24px; width:100%;">
    {ex_body}
  </div>
</div>

<!-- ── Errors 탭 ── -->
<div id="tab-errors" class="tab-pane">
  <div id="main-content" class="full" style="padding:24px; width:100%;">
    {err_body}
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
// ── 탭 전환 ──────────────────────────────────────────────────
function switchTab(name, btn) {{
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
  // URL hash 업데이트
  window.location.hash = name;
}}

// 페이지 로드 시 hash 탭 복원
window.addEventListener('load', () => {{
  const hash = window.location.hash.replace('#', '');
  if (['patterns', 'examples', 'errors'].includes(hash)) {{
    const btn = document.querySelector(`.tab-btn[onclick*="${{hash}}"]`);
    if (btn) switchTab(hash, btn);
  }}
}});

// ── Patterns 검색 ─────────────────────────────────────────────
function filterPatterns(q) {{
  q = q.toLowerCase().trim();
  document.querySelectorAll('.pattern-entry').forEach(el => {{
    const t = (el.id + el.textContent).toLowerCase();
    el.classList.toggle('hidden', q && !t.includes(q));
  }});
  document.querySelectorAll('.category-section').forEach(sec => {{
    const v = sec.querySelectorAll('.pattern-entry:not(.hidden)').length;
    sec.classList.toggle('all-hidden', v === 0);
  }});
}}

// ── Examples 태그 필터 ────────────────────────────────────────
function filterExamples(btn, tag) {{
  document.querySelectorAll('.tag-filter').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.example-entry').forEach(el => {{
    if (tag === 'all') {{ el.classList.remove('hidden'); return; }}
    if (tag === '__has_image__') {{
      el.classList.toggle('hidden', el.dataset.hasImage !== 'true');
      return;
    }}
    const tags = el.dataset.tags || '';
    el.classList.toggle('hidden', !tags.split(' ').includes(tag));
  }});
}}

// 페이지 로드 시 기본 필터: 이미지 있는 것만
window.addEventListener('load', () => {{
  const btn = document.querySelector('.tag-filter.active');
  if (btn && btn.textContent.includes('이미지')) {{
    filterExamples(btn, '__has_image__');
  }}
}});

// ── 전체 검색 ─────────────────────────────────────────────────
function globalSearch(q) {{
  q = q.toLowerCase().trim();
  if (!q) {{
    document.querySelectorAll('.entry').forEach(e => e.classList.remove('hidden'));
    return;
  }}
  document.querySelectorAll('.entry').forEach(el => {{
    el.classList.toggle('hidden', !el.textContent.toLowerCase().includes(q));
  }});
}}

// ── 코드 복사 ─────────────────────────────────────────────────
function copyCode(btn) {{
  const block = btn.closest('.nb-cell') || btn.closest('.code-block');
  const pre = block.querySelector('pre');
  if (!pre) return;
  navigator.clipboard.writeText(pre.textContent).then(() => {{
    btn.textContent = '복사✅';
    setTimeout(() => btn.textContent = '복사', 1500);
  }});
}}

// ── Notebook 탭 전환 ──────────────────────────────────────────
function switchNb(nbId, btn) {{
  document.querySelectorAll('.nb-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nb-tab').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById(nbId);
  if (panel) panel.classList.add('active');
  if (btn)   btn.classList.add('active');
}}

// ── 한/영 전환 ────────────────────────────────────────────────
function setLang(nbId, lang) {{
  const panel = document.getElementById(nbId);
  if (!panel) return;
  panel.dataset.lang = lang;

  // wrap 전환
  const koWrap = panel.querySelector('.lang-ko-wrap');
  const enWrap = panel.querySelector('.lang-en-wrap');
  if (koWrap) koWrap.style.display = lang === 'ko' ? '' : 'none';
  if (enWrap) enWrap.style.display = lang === 'en' ? '' : 'none';

  // 버튼 활성화
  const btnKo = document.getElementById(nbId + '-btn-ko');
  const btnEn = document.getElementById(nbId + '-btn-en');
  if (btnKo) btnKo.classList.toggle('active', lang === 'ko');
  if (btnEn) btnEn.classList.toggle('active', lang === 'en');

  // 해당 wrap의 markdown 렌더링 (아직 안 된 것만)
  const activeWrap = lang === 'ko' ? koWrap : enWrap;
  if (activeWrap) renderMarkdownIn(activeWrap);
}}

// ── Markdown 렌더링 (marked.js) ───────────────────────────────
function renderMarkdownIn(container) {{
  if (typeof marked === 'undefined') return;
  marked.setOptions({{ breaks: true, gfm: true, sanitize: false }});
  container.querySelectorAll('.nb-md[data-md]').forEach(el => {{
    const raw = el.getAttribute('data-md');
    el.innerHTML = marked.parse(raw);
    el.classList.add('nb-md-content');
    el.removeAttribute('data-md');
    el.querySelectorAll('pre code').forEach(block => {{
      if (typeof Prism !== 'undefined') Prism.highlightElement(block);
    }});
  }});
}}

function renderMarkdown() {{
  // 현재 보이는 패널의 기본 언어 wrap만 렌더링
  document.querySelectorAll('.nb-panel').forEach(panel => {{
    const lang = panel.dataset.lang || 'en';
    const wrap = panel.querySelector(`.lang-${{lang}}-wrap`);
    if (wrap) renderMarkdownIn(wrap);
  }});
  // code cell 하이라이트
  document.querySelectorAll('pre[class*="language-"]').forEach(el => {{
    if (typeof Prism !== 'undefined') Prism.highlightElement(el.querySelector('code') || el);
  }});
}}

window.addEventListener('load', () => {{
  // 탭 hash 복원
  const hash = window.location.hash.replace('#', '');
  if (['patterns','notebooks','examples','errors'].includes(hash)) {{
    const btn = document.querySelector(`.tab-btn[onclick*="${{hash}}"]`);
    if (btn) switchTab(hash, btn);
  }}
  // 이미지 필터 적용
  const activeFilter = document.querySelector('.tag-filter.active');
  if (activeFilter && activeFilter.textContent.includes('이미지')) {{
    filterExamples(activeFilter, '__has_image__');
  }}
  // Markdown 렌더링
  renderMarkdown();
}});
</script>
</body>
</html>"""
