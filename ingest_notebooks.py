#!/usr/bin/env python3
"""
meep 공식 GitHub ipynb 파일 파싱 → meep-kb DB notebooks 테이블 저장

실행:
  python3 ingest_notebooks.py
"""
import json, sqlite3, urllib.request, datetime, base64, re, os
from pathlib import Path

DB_PATH     = Path(os.environ.get("DB_PATH", "/app/db/knowledge.db"))
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/app/db/results"))
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── 수집할 ipynb 목록 ─────────────────────────────────────────────────────────
NOTEBOOKS = [
    {
        "title":    "01 - Introduction to Adjoint Optimization",
        "filename": "01-Introduction.ipynb",
        "url":      "https://raw.githubusercontent.com/NanoComp/meep/master/python/examples/adjoint_optimization/01-Introduction.ipynb",
        "tags":     "adjoint,optimization,introduction,meep,tutorial",
        "folder":   "adjoint_optimization",
    },
    {
        "title":    "02 - Waveguide Bend Optimization",
        "filename": "02-Waveguide_Bend.ipynb",
        "url":      "https://raw.githubusercontent.com/NanoComp/meep/master/python/examples/adjoint_optimization/02-Waveguide_Bend.ipynb",
        "tags":     "adjoint,optimization,waveguide,bend,meep,tutorial",
        "folder":   "adjoint_optimization",
    },
    {
        "title":    "03 - Filtered Waveguide Bend",
        "filename": "03-Filtered_Waveguide_Bend.ipynb",
        "url":      "https://raw.githubusercontent.com/NanoComp/meep/master/python/examples/adjoint_optimization/03-Filtered_Waveguide_Bend.ipynb",
        "tags":     "adjoint,optimization,waveguide,bend,filter,meep,tutorial",
        "folder":   "adjoint_optimization",
    },
    {
        "title":    "04 - Beam Splitter Optimization",
        "filename": "04-Splitter.ipynb",
        "url":      "https://raw.githubusercontent.com/NanoComp/meep/master/python/examples/adjoint_optimization/04-Splitter.ipynb",
        "tags":     "adjoint,optimization,splitter,meep,tutorial",
        "folder":   "adjoint_optimization",
    },
    {
        "title":    "05 - Near-to-Far Field",
        "filename": "05-Near2Far.ipynb",
        "url":      "https://raw.githubusercontent.com/NanoComp/meep/master/python/examples/adjoint_optimization/05-Near2Far.ipynb",
        "tags":     "adjoint,optimization,near2far,farfield,meep,tutorial",
        "folder":   "adjoint_optimization",
    },
    {
        "title":    "Bend Minimax",
        "filename": "Bend_Minimax.ipynb",
        "url":      "https://raw.githubusercontent.com/NanoComp/meep/master/python/examples/adjoint_optimization/Bend%20Minimax.ipynb",
        "tags":     "adjoint,optimization,bend,minimax,meep",
        "folder":   "adjoint_optimization",
    },
    {
        "title":    "Fourier Bend",
        "filename": "Fourier-Bend.ipynb",
        "url":      "https://raw.githubusercontent.com/NanoComp/meep/master/python/examples/adjoint_optimization/Fourier-Bend.ipynb",
        "tags":     "adjoint,optimization,fourier,bend,meep",
        "folder":   "adjoint_optimization",
    },
    {
        "title":    "Fourier Metalens",
        "filename": "Fourier-Metalens.ipynb",
        "url":      "https://raw.githubusercontent.com/NanoComp/meep/master/python/examples/adjoint_optimization/Fourier-Metalens.ipynb",
        "tags":     "adjoint,optimization,fourier,metalens,meep",
        "folder":   "adjoint_optimization",
    },
]


# ── DB 테이블 생성 ─────────────────────────────────────────────────────────────
def init_db(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS notebooks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        filename    TEXT,
        folder      TEXT,
        source_url  TEXT,
        tags        TEXT,
        cells       TEXT,      -- JSON: [{type, source, outputs:[{kind,data,text}]}]
        cell_count  INTEGER,
        code_count  INTEGER,
        image_count INTEGER,
        created_at  TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notebooks_folder ON notebooks(folder)")
    conn.commit()
    print("DB 테이블 준비 완료")


# ── ipynb 파싱 ────────────────────────────────────────────────────────────────
def parse_ipynb(raw: dict, notebook_id_prefix: str) -> list:
    """ipynb JSON → cells 리스트 반환
    각 cell: {type, source, outputs:[{kind, data_b64, text}]}
    """
    cells = []
    raw_cells = raw.get("cells", [])

    for i, cell in enumerate(raw_cells):
        cell_type = cell.get("cell_type", "code")  # markdown / code / raw
        source    = "".join(cell.get("source", []))

        # 빈 셀 스킵
        if not source.strip():
            continue

        parsed_outputs = []
        for out in cell.get("outputs", []):
            out_type = out.get("output_type", "")
            data     = out.get("data", {})

            # 이미지 추출 (PNG 우선, 그 다음 JPEG)
            for img_mime in ("image/png", "image/jpeg", "image/svg+xml"):
                if img_mime in data:
                    img_b64 = data[img_mime]
                    if isinstance(img_b64, list):
                        img_b64 = "".join(img_b64)
                    # 이미지 파일 저장
                    ext      = img_mime.split("/")[-1].replace("svg+xml", "svg")
                    img_name = f"nb_{notebook_id_prefix}_cell{i:03d}.{ext}"
                    img_path = RESULTS_DIR / img_name
                    try:
                        raw_bytes = base64.b64decode(img_b64)
                        img_path.write_bytes(raw_bytes)
                        parsed_outputs.append({
                            "kind":     "image",
                            "img_path": str(img_path),
                            "img_name": img_name,
                            "mime":     img_mime,
                        })
                    except Exception as e:
                        print(f"    [WARN] 이미지 저장 실패: {e}")
                    break

            # 텍스트 출력 (stream / execute_result / error)
            text_parts = []
            if "text" in out:
                text_parts = out["text"] if isinstance(out["text"], list) else [out["text"]]
            elif "text/plain" in data:
                tp = data["text/plain"]
                text_parts = tp if isinstance(tp, list) else [tp]
            if out_type == "error":
                tb = out.get("traceback", [])
                # ANSI 코드 제거
                ansi = re.compile(r'\x1B\[[0-9;]*[mK]')
                text_parts = [ansi.sub("", "\n".join(tb))]

            if text_parts:
                parsed_outputs.append({
                    "kind": "text",
                    "text": "".join(text_parts)[:2000],
                    "is_error": out_type == "error",
                })

        cells.append({
            "type":    cell_type,
            "source":  source,
            "outputs": parsed_outputs,
        })

    return cells


# ── 다운로드 + 저장 ───────────────────────────────────────────────────────────
def ingest_notebook(nb_meta: dict, conn) -> int:
    title    = nb_meta["title"]
    filename = nb_meta["filename"]
    url      = nb_meta["url"]

    print(f"\n  [{filename}]")
    print(f"  URL: {url[:70]}")

    # 이미 존재하는지 확인
    existing = conn.execute(
        "SELECT id FROM notebooks WHERE filename=?", (filename,)
    ).fetchone()
    if existing:
        print(f"  → 이미 존재 (id={existing[0]}), 건너뜀")
        return existing[0]

    # 다운로드
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = json.loads(r.read())
        print(f"  다운로드 완료 ({len(json.dumps(raw)):,} bytes)")
    except Exception as e:
        print(f"  ❌ 다운로드 실패: {e}")
        return None

    # 파싱
    nb_id_prefix = filename.replace(".ipynb", "").replace(" ", "_")
    cells        = parse_ipynb(raw, nb_id_prefix)

    code_count  = sum(1 for c in cells if c["type"] == "code")
    image_count = sum(
        sum(1 for o in c["outputs"] if o["kind"] == "image")
        for c in cells
    )

    print(f"  셀: {len(cells)}개 (코드={code_count}, 이미지={image_count}개)")

    # DB 저장
    conn.execute(
        """INSERT INTO notebooks
           (title, filename, folder, source_url, tags, cells,
            cell_count, code_count, image_count, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            title, filename, nb_meta.get("folder",""),
            url, nb_meta.get("tags",""),
            json.dumps(cells, ensure_ascii=False),
            len(cells), code_count, image_count,
            datetime.datetime.now().isoformat(),
        )
    )
    conn.commit()
    nb_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"  ✅ 저장 완료 (id={nb_id})")
    return nb_id


def main():
    print("="*62)
    print("MEEP ipynb 수집기")
    print(f"DB: {DB_PATH}")
    print("="*62)

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    init_db(conn)

    saved = 0
    for nb in NOTEBOOKS:
        nb_id = ingest_notebook(nb, conn)
        if nb_id:
            saved += 1

    # 요약
    rows = conn.execute(
        "SELECT id, title, cell_count, code_count, image_count FROM notebooks ORDER BY id"
    ).fetchall()
    print(f"\n{'='*62}")
    print(f"완료! 총 {len(rows)}개 노트북 저장됨")
    for r in rows:
        print(f"  id={r[0]} | {r[1][:50]} | cells={r[2]}, code={r[3]}, imgs={r[4]}")
    conn.close()


if __name__ == "__main__":
    main()
