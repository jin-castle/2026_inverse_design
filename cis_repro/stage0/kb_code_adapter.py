"""
Mode B: meep-kb에서 유사 코드 검색 + 파라미터 치환
==================================================
논문 구조(pillar_mask 등)는 있지만 코드가 없을 때:
  1. meep-kb examples에서 동일 design_type CIS 코드 검색
  2. 파라미터(SP_size, FL, Layer_t, resolution) 치환
  3. pillar_mask 교체 (있으면)
"""
import sqlite3, re, json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "db" / "knowledge.db"


def find_similar(params: dict) -> str | None:
    """meep-kb에서 동일 design_type CIS 코드 검색"""
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()
    dt   = params.get("design_type", "discrete_pillar")
    mat  = params.get("material_name", "")

    # design_type + cis 태그로 우선 검색
    cur.execute("""
        SELECT code FROM examples
        WHERE tags LIKE ? AND tags LIKE '%cis%'
        AND code IS NOT NULL AND LENGTH(code) > 500
        ORDER BY created_at DESC LIMIT 1
    """, (f"%{dt}%",))
    row = cur.fetchone()

    if not row and mat:
        # material로 폴백
        cur.execute("""
            SELECT code FROM examples
            WHERE tags LIKE '%cis%' AND tags LIKE ?
            AND code IS NOT NULL AND LENGTH(code) > 500
            ORDER BY created_at DESC LIMIT 1
        """, (f"%{mat}%",))
        row = cur.fetchone()

    if not row:
        # cis 태그만으로 폴백
        cur.execute("""
            SELECT code FROM examples
            WHERE tags LIKE '%cis%'
            AND code IS NOT NULL AND LENGTH(code) > 500
            ORDER BY created_at DESC LIMIT 1
        """)
        row = cur.fetchone()

    conn.close()
    return row[0] if row else None


def adapt_code(template_code: str, params: dict) -> str:
    """핵심 파라미터 치환"""
    code = template_code

    # 파라미터 치환 맵
    subs = [
        (r'\bSP_size\s*=\s*[\d.]+',         f"SP_size         = {params['SP_size']}"),
        (r'\bLayer_thickness\s*=\s*[\d.]+',  f"Layer_thickness = {params['Layer_thickness']}"),
        (r'\bFL_thickness\s*=\s*[\d.]+',     f"FL_thickness    = {params['FL_thickness']}"),
        (r'\bresolution\s*=\s*\d+',           f"resolution      = {params['resolution']}"),
    ]
    if params.get("n_material"):
        mat = params.get("material_name", "TiO2")
        subs.append((rf'\b{mat}\s*=\s*mp\.Medium\(index=[\d.]+\)',
                     f'{mat} = mp.Medium(index={params["n_material"]})'))
    if params.get("focal_material"):
        focal = params["focal_material"]
        subs.append((r'(Focal Layer.*?material=)\w+',
                     rf'\g<1>{focal}'))

    for pat, rep in subs:
        code = re.sub(pat, rep, code, count=1)

    # pillar_mask + grid_n 교체 (N도 반드시 함께 교체)
    if params.get("pillar_mask"):
        mask = params["pillar_mask"]
        N    = params.get("grid_n", len(mask))
        Nc   = len(mask[0]) if mask else N
        mask_str = json.dumps(mask)
        # pillar_mask 교체 (다양한 패턴 대응)
        code = re.sub(
            r'pillar_mask\s*=\s*\[[\s\S]*?\n\]',
            f"pillar_mask = {mask_str}",
            code, count=1
        )
        # Nx, Ny, N 교체
        code = re.sub(r'\bNx\s*=\s*\d+', f"Nx = {N}", code, count=1)
        code = re.sub(r'\bNy\s*=\s*\d+', f"Ny = {Nc}", code, count=1)
        # for loop range 교체: _i/_j 변수 또는 i/j 변수 모두 대응
        code = re.sub(r'for\s+_i\s+in\s+range\(\d+\)', f"for _i in range({N})", code)
        code = re.sub(r'for\s+_j\s+in\s+range\(\d+\)', f"for _j in range({Nc})", code)
        code = re.sub(r'for\s+i\s+in\s+range\(\d+\):', f"for i in range({N}):", code)
        code = re.sub(r'for\s+j\s+in\s+range\(\d+\):', f"for j in range({Nc}):", code)
        # -N/2 * w 계산에서 하드코딩된 숫자(10, 8 등) 교체
        code = re.sub(r'round\(-\d+\s*\*\s*w\s*\+', f"round(-{N//2}*w +", code)
        code = re.sub(r'round\(\s*\d+\s*\*\s*w\s*-', f"round({N//2}*w -", code)

    # tile_w 교체
    if params.get("tile_w"):
        code = re.sub(r'\bw\s*=\s*[\d.]+\s*#.*?tile', f"w = {params['tile_w']}  # tile", code, count=1)
        code = re.sub(r'\bw\s*=\s*[\d.]+(?=\s*# μm)', f"w = {params['tile_w']}", code, count=1)

    return code


def run(params: dict) -> str | None:
    """검색 + 치환 통합 실행. 실패시 None 반환."""
    try:
        template = find_similar(params)
        if template is None:
            print("  [Mode B] KB 유사 코드 없음 → Mode C(역설계)로 폴백")
            return None
        adapted = adapt_code(template, params)
        print(f"  [Mode B] KB 코드 적용 완료 ({len(adapted)}자)")
        return adapted
    except Exception as e:
        print(f"  [Mode B] 오류: {e}")
        return None
