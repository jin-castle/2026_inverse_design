#!/usr/bin/env python3
"""
MEEP 핵심 개념 15개를 LLM으로 생성하여 concepts 테이블에 저장.
Usage: python -X utf8 tools/generate_concepts.py [--concept PML] [--all]
"""
import os, sys, json, re, sqlite3, time, argparse
from pathlib import Path
from dotenv import load_dotenv

# .env 로드
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

CONCEPTS = [
    {
        "name": "PML",
        "name_ko": "완전 흡수 경계 조건",
        "aliases": ["perfectly matched layer", "absorbing boundary"],
        "category": "boundary",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Perfectly_Matched_Layer/",
        "demo_hint": "1D 파동 전파 + PML 흡수 시각화. Ez 필드가 PML 영역에서 감쇠되는 것을 보여줄 것",
    },
    {
        "name": "EigenmodeSource",
        "name_ko": "고유모드 소스",
        "aliases": ["EigenModeSource", "eigenmode", "waveguide mode source"],
        "category": "source",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#eigenmodesource",
        "demo_hint": "TE0 모드 도파관 전파. eig_band=1로 TE0 여기, flux로 투과율 측정",
    },
    {
        "name": "FluxRegion",
        "name_ko": "에너지 플럭스 측정 영역",
        "aliases": ["flux monitor", "add_flux", "transmission", "reflection"],
        "category": "monitor",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#flux-spectra",
        "demo_hint": "투과/반사 스펙트럼 측정. 정규화 런 + 측정 런으로 T/R 계산",
    },
    {
        "name": "resolution",
        "name_ko": "격자 해상도",
        "aliases": ["grid resolution", "pixels per micron", "spatial discretization"],
        "category": "simulation",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Introduction/#units-and-resolution",
        "demo_hint": "resolution 10 vs 50 비교. 같은 시뮬레이션을 다른 resolution으로 실행해서 수렴성 보여주기",
    },
    {
        "name": "GaussianSource",
        "name_ko": "가우시안 소스",
        "aliases": ["gaussian pulse", "broadband source", "ContinuousSource"],
        "category": "source",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#gaussiansource",
        "demo_hint": "가우시안 펄스 시간 프로파일 + 주파수 스펙트럼 (FFT). fcen, fwidth 파라미터 효과",
    },
    {
        "name": "Harminv",
        "name_ko": "하모닉 인버전 (공진 모드 분석)",
        "aliases": ["harminv", "resonance", "quality factor", "Q factor"],
        "category": "analysis",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#harminv",
        "demo_hint": "링 공진기 Q factor 측정. Harminv로 공진 주파수와 Q 추출",
    },
    {
        "name": "Symmetry",
        "name_ko": "대칭 조건",
        "aliases": ["Mirror symmetry", "EVEN_Y", "ODD_Z", "symmetry reduction"],
        "category": "simulation",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#symmetry",
        "demo_hint": "대칭 조건으로 계산 절반 감소. Mirror(Y) 적용 전후 속도/메모리 비교",
    },
    {
        "name": "DFT",
        "name_ko": "이산 푸리에 변환 필드",
        "aliases": ["dft fields", "frequency domain", "add_dft_fields", "near-field"],
        "category": "monitor",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#dft-fields",
        "demo_hint": "주파수 도메인 전자기장 분포 시각화. |Ez|^2 필드 플롯",
    },
    {
        "name": "MaterialGrid",
        "name_ko": "재료 격자 (역설계용)",
        "aliases": ["MaterialGrid", "design variable", "topology optimization", "inverse design"],
        "category": "optimization",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#materialgrid",
        "demo_hint": "2D 역설계 기본 구조. MaterialGrid 정의 + 초기 구조 시각화",
    },
    {
        "name": "adjoint",
        "name_ko": "어드조인트 최적화",
        "aliases": ["adjoint method", "OptimizationProblem", "gradient", "inverse design adjoint"],
        "category": "optimization",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/AdjointSolver/",
        "demo_hint": "FOM + gradient 계산 1회. ∂FOM/∂ε 계산 원리 설명",
    },
    {
        "name": "eig_band",
        "name_ko": "고유모드 밴드 번호",
        "aliases": ["eig_band", "mode number", "TE0", "TE1", "TM"],
        "category": "source",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#eigenmodesource",
        "demo_hint": "eig_band=1(TE0) vs eig_band=2(TE1) 모드 프로파일 비교",
    },
    {
        "name": "stop_when_fields_decayed",
        "name_ko": "필드 수렴 종료 조건",
        "aliases": ["stop_when_fields_decayed", "run until", "convergence"],
        "category": "simulation",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#run-and-step-functions",
        "demo_hint": "fixed until vs stop_when_fields_decayed 비교. 수렴 시간 차이",
    },
    {
        "name": "MPB",
        "name_ko": "포토닉 밴드 구조 계산",
        "aliases": ["MPB", "band structure", "photonic crystal", "dispersion"],
        "category": "analysis",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Scheme_Tutorials/Band_Diagram,_Resonant_Modes,_and_Transmission_in_a_Photonic_Crystal_Waveguide/",
        "demo_hint": "1D 포토닉 결정 밴드 구조. MPB로 밴드갭 계산",
    },
    {
        "name": "near2far",
        "name_ko": "근거리-원거리 변환",
        "aliases": ["near2far", "far field", "radiation pattern", "add_near2far"],
        "category": "monitor",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#near-to-far-field-spectra",
        "demo_hint": "안테나 방사 패턴 계산. near2far로 far-field 방사 패턴 플롯",
    },
    {
        "name": "courant",
        "name_ko": "쿠란트 수 (수치 안정성 조건)",
        "aliases": ["courant number", "CFL", "dt", "timestep", "numerical stability"],
        "category": "simulation",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Introduction/#the-courant-factor-and-time-step",
        "demo_hint": "쿠란트 조건 설명 + courant=0.3 vs 0.5 안정성 비교",
    },
]


PROMPT_TEMPLATE = """당신은 MEEP FDTD 시뮬레이션 전문가이자 교수입니다.
MEEP의 "{name}" ({name_ko}) 개념을 설명해주세요.

참고 URL: {doc_url}
카테고리: {category}
난이도: {difficulty}
데모 힌트: {demo_hint}

다음 형식으로 작성하세요:

SUMMARY:
[1~2문장 핵심 요약. 비전문가도 이해할 수 있게]

EXPLANATION:
[상세 설명 (마크다운 형식, 한국어)
- 물리/수학적 원리 (수식 포함, LaTeX 형식: $수식$)
- MEEP에서 어떻게 구현되어 있는지
- 파라미터 설명
- 언제 사용하는지]

PHYSICS_BACKGROUND:
[수식 중심의 물리 배경 설명
예: PML은 복소 좌표 변환 $\\tilde{{x}} = x(1 + i\\sigma/\\omega)$을 사용하여...]

COMMON_MISTAKES:
["실수 1: ...", "실수 2: ...", "실수 3: ..."]

RELATED_CONCEPTS:
["개념1", "개념2"]

DEMO_CODE:
```python
# {demo_hint}
# 완전히 독립 실행 가능한 코드 (import부터 결과 출력까지)
# matplotlib.use('Agg') 필수
# plt.savefig('output.png') 로 이미지 저장
# 100줄 이내, resolution=10~20 (빠른 실행)
import meep as mp
...
```

DEMO_DESCRIPTION:
[코드가 보여주는 것 설명. 실행 결과로 무엇을 볼 수 있는지]
"""


def parse_response(text: str) -> dict:
    """
    LLM 응답 파싱.
    LLM이 ## SUMMARY: 식 마크다운 헤더를 붙이는 경우도 처리.
    """
    result = {}

    SECTION_TAGS = [
        "SUMMARY", "EXPLANATION", "PHYSICS_BACKGROUND",
        "COMMON_MISTAKES", "RELATED_CONCEPTS", "DEMO_CODE", "DEMO_DESCRIPTION"
    ]

    # 각 섹션의 시작 위치 찾기
    section_positions = {}
    for tag in SECTION_TAGS:
        # tag: 형태 (마크다운 헤더 선택적, --- 구분선 선택적)
        m = re.search(rf'(?m)^[#\-]*\s*{tag}\s*:\s*$', text)
        if not m:
            # 같은 줄에 내용이 있는 경우: SUMMARY: 내용...
            m = re.search(rf'(?m)^[#\-]*\s*{tag}\s*:', text)
        if m:
            section_positions[tag] = m.end()

    def get_section(tag: str) -> str:
        if tag not in section_positions:
            return ""
        start = section_positions[tag]

        # 다음 섹션 위치 찾기
        end = len(text)
        for other_tag in SECTION_TAGS:
            if other_tag != tag and other_tag in section_positions:
                pos = section_positions[other_tag]
                # 현재 섹션 이후에 있는 가장 가까운 섹션
                # 섹션 헤더 자체 위치 (콜론 앞) 계산 필요
                # section_positions에는 콜론 이후 위치가 저장되어 있음
                # 헤더 길이를 감안해 적당히 처리
                header_start = text.rfind(other_tag, 0, pos)
                if header_start > start and header_start < end:
                    # 마크다운 헤더 시작까지 찾기
                    line_start = text.rfind('\n', 0, header_start)
                    if line_start == -1:
                        line_start = 0
                    else:
                        line_start += 1
                    end = min(end, line_start)

        return text[start:end].strip()

    def clean_section(s: str) -> str:
        """구분선(---, ===) 제거 후 정리"""
        s = re.sub(r'\n?---+\s*$', '', s).strip()
        s = re.sub(r'\n?===+\s*$', '', s).strip()
        return s

    result["summary"] = clean_section(get_section("SUMMARY"))
    result["explanation"] = clean_section(get_section("EXPLANATION"))
    result["physics_background"] = clean_section(get_section("PHYSICS_BACKGROUND"))
    result["demo_description"] = clean_section(get_section("DEMO_DESCRIPTION"))

    # COMMON_MISTAKES: JSON array 파싱
    cm_text = clean_section(get_section("COMMON_MISTAKES"))
    try:
        # JSON array 찾기 (멀티라인 지원)
        m = re.search(r'\[[\s\S]*?\]', cm_text)
        if m:
            result["common_mistakes"] = json.dumps(json.loads(m.group(0)), ensure_ascii=False)
        else:
            # 줄 단위 파싱 fallback: "- ..." 또는 "실수..." 형식
            lines = []
            for l in cm_text.split('\n'):
                l = l.strip().lstrip('-').lstrip('*').strip().strip('"').strip("'").rstrip(',')
                if l and l not in ['[', ']']:
                    lines.append(l)
            result["common_mistakes"] = json.dumps(lines[:5], ensure_ascii=False)
    except:
        result["common_mistakes"] = json.dumps([cm_text[:200]] if cm_text else [], ensure_ascii=False)

    # RELATED_CONCEPTS: JSON array 파싱
    rc_text = clean_section(get_section("RELATED_CONCEPTS"))
    try:
        m = re.search(r'\[[\s\S]*?\]', rc_text)
        if m:
            result["related_concepts"] = json.dumps(json.loads(m.group(0)), ensure_ascii=False)
        else:
            lines = []
            for l in rc_text.split('\n'):
                l = l.strip().lstrip('-').lstrip('*').strip().strip('"').strip("'").rstrip(',')
                if l and l not in ['[', ']']:
                    lines.append(l)
            result["related_concepts"] = json.dumps(lines[:8], ensure_ascii=False)
    except:
        result["related_concepts"] = json.dumps([], ensure_ascii=False)

    # DEMO_CODE: ```python ... ``` 블록 추출
    m = re.search(r'DEMO_CODE:\s*\n```python\n(.*?)```', text, re.DOTALL)
    if not m:
        m = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    result["demo_code"] = m.group(1).strip() if m else ""

    return result


def generate_concept(concept: dict, api_key: str) -> dict:
    """단일 개념을 LLM으로 생성"""
    import anthropic

    prompt = PROMPT_TEMPLATE.format(
        name=concept["name"],
        name_ko=concept["name_ko"],
        doc_url=concept["doc_url"],
        category=concept["category"],
        difficulty=concept["difficulty"],
        demo_hint=concept["demo_hint"],
    )

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = msg.content[0].text
    parsed = parse_response(response_text)
    return parsed


def save_concept(conn: sqlite3.Connection, concept: dict, parsed: dict):
    """concepts 테이블에 INSERT (UPSERT)"""
    conn.execute("""
        INSERT INTO concepts
            (name, name_ko, aliases, category, difficulty,
             summary, explanation, physics_background, common_mistakes, related_concepts,
             demo_code, demo_description,
             result_status, meep_version, doc_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '1.31.0', ?)
        ON CONFLICT(name) DO UPDATE SET
            name_ko=excluded.name_ko,
            aliases=excluded.aliases,
            category=excluded.category,
            difficulty=excluded.difficulty,
            summary=excluded.summary,
            explanation=excluded.explanation,
            physics_background=excluded.physics_background,
            common_mistakes=excluded.common_mistakes,
            related_concepts=excluded.related_concepts,
            demo_code=excluded.demo_code,
            demo_description=excluded.demo_description,
            doc_url=excluded.doc_url,
            updated_at=CURRENT_TIMESTAMP
    """, (
        concept["name"],
        concept["name_ko"],
        json.dumps(concept["aliases"], ensure_ascii=False),
        concept["category"],
        concept["difficulty"],
        parsed.get("summary", ""),
        parsed.get("explanation", ""),
        parsed.get("physics_background", ""),
        parsed.get("common_mistakes", "[]"),
        parsed.get("related_concepts", "[]"),
        parsed.get("demo_code", ""),
        parsed.get("demo_description", ""),
        concept["doc_url"],
    ))
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concept", help="특정 개념만 생성 (예: PML)")
    parser.add_argument("--all", action="store_true", help="모든 개념 생성 (default)")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="이미 있는 개념 건너뜀")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY가 없습니다.")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=10)

    # 처리할 개념 목록 결정
    if args.concept:
        targets = [c for c in CONCEPTS if c["name"].lower() == args.concept.lower()]
        if not targets:
            print(f"[ERROR] 개념 '{args.concept}'을 찾지 못했습니다.")
            sys.exit(1)
    else:
        targets = CONCEPTS

    total = len(targets)
    success = 0
    errors = []

    for i, concept in enumerate(targets):
        name = concept["name"]

        # 기존 항목 확인
        if args.skip_existing:
            existing = conn.execute(
                "SELECT summary FROM concepts WHERE name=? AND summary IS NOT NULL AND LENGTH(summary) > 10",
                (name,)
            ).fetchone()
            if existing:
                print(f"[{i+1}/{total}] ⏭️ {name} (already exists, skipping)")
                success += 1
                continue

        print(f"[{i+1}/{total}] 🔄 {name} ({concept['name_ko']}) 생성 중...")
        try:
            parsed = generate_concept(concept, api_key)

            # 기본 검증
            if not parsed.get("summary") or len(parsed["summary"]) < 20:
                print(f"  WARNING summary가 너무 짧습니다: {repr(parsed.get('summary',''))[:50]}")

            save_concept(conn, concept, parsed)
            print(f"  OK 저장 완료 (summary: {len(parsed.get('summary',''))}자, code: {len(parsed.get('demo_code',''))}자)")
            success += 1

            # API rate limit 방지
            if i < total - 1:
                time.sleep(1)

        except Exception as e:
            print(f"  FAIL 실패: {e}")
            errors.append((name, str(e)))

    conn.close()

    print(f"\n=== 완료: {success}/{total} ===")
    if errors:
        print("실패 목록:")
        for name, err in errors:
            print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()
