"""
physics_enricher.py - MEEP 에러 물리 원인 LLM 자동 분석 보강

Usage:
    python -X utf8 tools/physics_enricher.py [--limit N] [--dry-run] [--model haiku|sonnet]
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).parent.parent / ".env"))

import anthropic

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

PHYSICS_HINTS = {
    "Divergence": """
    MEEP 발산 원인:
    - Courant 조건: dt < dx/(c√D). resolution 낮으면 dt 자동 증가 → 발산
    - PML 흡수 불충분: 파장보다 얇은 PML → 반사 → 에너지 축적
    - 고유전율 재료(ε>20): resolution 부족 시 격자 분산 오류
    """,
    "EigenMode": """
    EigenmodeSource 물리:
    - eig_band: 1-indexed (0은 정의 안됨 → T>100% 또는 오류)
    - eig_parity: EVEN_Y+ODD_Z = TE (Ey dominant), ODD_Y+EVEN_Z = TM
    - 소스 크기: 도파관보다 충분히 커야 모드가 완전히 포함됨
    """,
    "PML": """
    PML(Perfectly Matched Layer) 물리:
    - PML은 복소 좌표 변환으로 인위적 감쇠를 추가
    - PML 내부의 필드는 물리적 의미 없음 → monitor 배치 금지
    - PML 두께: 최소 파장의 1배, 권장 2배
    - 소스가 PML 근처에 있으면 evanescent field 오염
    """,
    "MPIError": """
    MPI 병렬화 물리:
    - MEEP MPI: 시뮬레이션 셀을 rank별로 분할
    - collective 연산(get_array, get_fluxes): 모든 rank 동시 실행 필수
    - rank 불균형: 일부만 collective → deadlock
    """,
    "MPIDeadlockRisk": """
    MPI 병렬화 물리:
    - MEEP MPI: 시뮬레이션 셀을 rank별로 분할
    - collective 연산(sim.run, get_array, get_fluxes): 모든 rank 동시 실행 필수
    - try-except 블록 안에서 MPI collective 호출 시 일부 rank만 exception → deadlock
    - rank 불균형: 일부만 collective → 무한 대기 상태
    """,
    "Adjoint": """
    Adjoint 최적화 물리:
    - adjoint method: ∂FOM/∂ε = Re(E_adj* × ∂M/∂ε × E_fwd)
    - forward/adjoint run은 동일한 geometry에서 수행해야 함
    - reset_meep() 타이밍: forward fields 초기화 전에 adjoint 계산
    """,
    "Harminv": """
    Harminv (고조파 역문제) 물리:
    - Harminv는 FDTD 시간 신호에서 공진 주파수/Q를 추출하는 알고리즘
    - 신호가 충분히 감쇠되지 않으면 수렴 실패 → AssertionError
    - 시뮬레이션 시간이 너무 짧거나, Q가 매우 높으면 신호가 미감쇠 상태로 종료
    - run_time > 5 * Q / (2π * f) 이상 필요
    """,
    "AttributeError": """
    MEEP API 사용 물리:
    - MEEP Simulation 객체는 특정 속성만 제공 (API 문서 참조)
    - run_mode 속성은 MEEP API에 존재하지 않음 (사용자 정의 변수와 혼동)
    - MEEP 시뮬레이션의 실행 흐름: setup → fields initialization → time stepping
    """,
    "TypeError": """
    MEEP API 버전 변경:
    - MEEP MaterialGrid API는 버전별로 파라미터명이 변경됨
    - design_parameters는 구버전 API 인수, 신버전에서는 다른 인수 사용
    - API 변경으로 인한 하위 호환성 문제
    """,
}

# error_type → hint 키 매핑 (부분 매칭 포함)
def get_hint(error_type: str, error_message: str = "") -> str:
    if not error_type:
        # 메시지로 추론
        msg = (error_message or "").lower()
        if "t>100" in msg or "t > 100" in msg:
            return PHYSICS_HINTS.get("EigenMode", "")
        return ""

    for key in PHYSICS_HINTS:
        if key.lower() in error_type.lower():
            return PHYSICS_HINTS[key]

    # error_message 기반 추론
    msg = (error_message or "").lower()
    if "diverge" in msg or "nan" in msg:
        return PHYSICS_HINTS.get("Divergence", "")
    if "eigensource" in msg or "eigenmode" in msg:
        return PHYSICS_HINTS.get("EigenMode", "")
    if "pml" in msg:
        return PHYSICS_HINTS.get("PML", "")
    if "mpi" in msg or "deadlock" in msg:
        return PHYSICS_HINTS.get("MPIError", "")
    if "adjoint" in msg:
        return PHYSICS_HINTS.get("Adjoint", "")
    if "harminv" in msg:
        return PHYSICS_HINTS.get("Harminv", "")

    return ""


def build_prompt(row: dict) -> str:
    # trigger_code 또는 original_code 첫 50줄
    code_snippet = row.get("trigger_code") or ""
    if not code_snippet and row.get("original_code"):
        lines = (row["original_code"] or "").split("\n")[:50]
        code_snippet = "\n".join(lines)

    hint = get_hint(row.get("error_type", ""), row.get("error_message", ""))

    # symptom이 비어있으면 error_class로 추론
    symptom = row.get("symptom") or ""
    if not symptom:
        ec = row.get("error_class", "")
        if ec == "physics_error":
            symptom = "물리적 이상 결과 (T>100% 등)"
        elif ec == "numerical_error":
            symptom = "수치 발산 또는 NaN"
        else:
            symptom = "에러 발생"

    prompt = f"""당신은 MEEP FDTD 시뮬레이션 전문가입니다. 아래 에러를 분석해서
물리적 원인과 코드 원인을 한국어로 설명해주세요.

## 에러 분류
- error_class: {row.get('error_class', 'unknown')}  (code_error/physics_error/numerical_error/config_error)
- error_type: {row.get('error_type', 'unknown')}
- symptom: {symptom}

## 시뮬레이션 환경
- run_mode: {row.get('run_mode', 'unknown')}
- device_type: {row.get('device_type', 'unknown')}
- resolution: {row.get('resolution', 'unknown')}
- pml_thickness: {row.get('pml_thickness', 'unknown')} μm
- wavelength_um: {row.get('wavelength_um', 'unknown')} μm
- dim: {row.get('dim', 'unknown')}D

## 에러 메시지
{row.get('error_message', '(없음)')}

## 관련 코드 (에러 발생 부분)
{code_snippet or '(코드 없음)'}
"""

    if hint:
        prompt += f"""
## 물리 배경 지식 (참고)
{hint}
"""

    prompt += """
## 요청
다음 3가지를 반드시 아래 형식으로 작성하세요 (각 섹션은 반드시 해당 키워드로 시작):

PHYSICS_CAUSE:
[전자기학/광학 관점에서 이 에러가 왜 발생하는지 설명.
 단순 "코드가 잘못됨"이 아니라 물리 법칙 관점에서 설명.
 2~4문장, 물리 수식 포함 권장. 최소 50자 이상]

CODE_CAUSE:
[구체적으로 어떤 코드/파라미터 설정이 문제인지.
 1~2문장, 구체적 수치 포함 권장. 최소 20자 이상]

ROOT_CAUSE_CHAIN:
[JSON 배열 형식으로 원인 체인 (3~5단계)]
[
  {"level": 1, "cause": "증상"},
  {"level": 2, "cause": "직접 원인"},
  {"level": 3, "cause": "근본 원인"}
]
"""
    return prompt


def parse_response(text: str) -> dict:
    """LLM 응답에서 PHYSICS_CAUSE, CODE_CAUSE, ROOT_CAUSE_CHAIN 추출"""
    result = {}

    # PHYSICS_CAUSE 추출
    m = re.search(r"PHYSICS_CAUSE:\s*\n?(.*?)(?=\n\s*CODE_CAUSE:|$)", text, re.DOTALL | re.IGNORECASE)
    if m:
        result["physics_cause"] = m.group(1).strip()

    # CODE_CAUSE 추출
    m = re.search(r"CODE_CAUSE:\s*\n?(.*?)(?=\n\s*ROOT_CAUSE_CHAIN:|$)", text, re.DOTALL | re.IGNORECASE)
    if m:
        result["code_cause"] = m.group(1).strip()

    # ROOT_CAUSE_CHAIN 추출 (JSON 배열)
    m = re.search(r"ROOT_CAUSE_CHAIN:\s*\n?(.*?)$", text, re.DOTALL | re.IGNORECASE)
    if m:
        chain_text = m.group(1).strip()
        # JSON 배열 부분만 추출
        json_m = re.search(r"\[.*?\]", chain_text, re.DOTALL)
        if json_m:
            try:
                chain_json = json.loads(json_m.group(0))
                result["root_cause_chain"] = json.dumps(chain_json, ensure_ascii=False)
            except json.JSONDecodeError:
                result["root_cause_chain"] = chain_text[:500]
        else:
            result["root_cause_chain"] = chain_text[:500]

    return result


def enrich_record(client: anthropic.Anthropic, row: dict, model: str, dry_run: bool = False) -> dict | None:
    """단일 레코드를 LLM으로 분석하여 physics_cause, code_cause, root_cause_chain 반환"""
    prompt = build_prompt(row)

    if dry_run:
        print(f"  [DRY-RUN] id={row['id']}, model={model}")
        print(f"  prompt_len={len(prompt)}")
        return None

    model_id = "claude-haiku-4-5" if model == "haiku" else "claude-sonnet-4-5"

    try:
        response = client.messages.create(
            model=model_id,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
    except Exception as e:
        print(f"  [ERROR] API 호출 실패 id={row['id']}: {e}", file=sys.stderr)
        return None

    parsed = parse_response(text)

    # 품질 체크
    physics_cause = parsed.get("physics_cause", "")
    code_cause = parsed.get("code_cause", "")

    if len(physics_cause) < 50 or len(code_cause) < 20:
        if model == "haiku":
            print(f"  [RETRY] id={row['id']} haiku 품질 부족 → sonnet 재시도")
            return enrich_record(client, row, "sonnet", dry_run)
        else:
            print(f"  [WARN] id={row['id']} 품질 기준 미달 (physics={len(physics_cause)}자, code={len(code_cause)}자)")

    return parsed


def get_records(conn: sqlite3.Connection, limit: int | None = None) -> list[dict]:
    sql = """
    SELECT id, error_class, error_type, error_message, traceback_full,
           symptom, trigger_code, run_mode, device_type,
           resolution, pml_thickness, wavelength_um, dim,
           uses_adjoint, original_code, physics_cause, code_cause,
           root_cause_chain
    FROM sim_errors_v2
    WHERE (physics_cause IS NULL OR physics_cause = '')
       OR (code_cause IS NULL OR code_cause = '')
    ORDER BY id
    """
    if limit:
        sql += f" LIMIT {limit}"

    cursor = conn.execute(sql)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def update_record(conn: sqlite3.Connection, row_id: int, parsed: dict):
    conn.execute(
        """
        UPDATE sim_errors_v2
        SET physics_cause = ?, code_cause = ?, root_cause_chain = ?
        WHERE id = ?
        """,
        (
            parsed.get("physics_cause", ""),
            parsed.get("code_cause", ""),
            parsed.get("root_cause_chain", ""),
            row_id,
        ),
    )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="MEEP 에러 물리 원인 LLM 자동 보강")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 레코드 수")
    parser.add_argument("--dry-run", action="store_true", help="DB 업데이트 없이 출력만")
    parser.add_argument("--model", choices=["haiku", "sonnet"], default="haiku", help="LLM 모델 선택")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    conn = sqlite3.connect(str(DB_PATH))

    records = get_records(conn, args.limit)
    print(f"대상 레코드: {len(records)}개")

    if args.dry_run:
        print("\n[DRY-RUN 모드] DB 업데이트 없이 대상 목록만 출력:\n")
        for row in records:
            print(f"  id={row['id']}, error_class={row['error_class']}, error_type={row['error_type']}")
            print(f"    error_message={str(row['error_message'])[:80]}")
            print(f"    symptom={row['symptom']}")
        conn.close()
        return

    success = 0
    failed = 0

    for i, row in enumerate(records):
        print(f"\n[{i+1}/{len(records)}] id={row['id']}, error_type={row['error_type']}, error_class={row['error_class']}")
        parsed = enrich_record(client, row, args.model, args.dry_run)

        if parsed:
            update_record(conn, row["id"], parsed)
            pc = parsed.get("physics_cause", "")
            cc = parsed.get("code_cause", "")
            rcc = parsed.get("root_cause_chain", "")
            print(f"  → physics_cause ({len(pc)}자): {pc[:80]}...")
            print(f"  → code_cause ({len(cc)}자): {cc[:60]}...")
            print(f"  → root_cause_chain: {rcc[:60]}...")
            success += 1
        else:
            print(f"  → [SKIP] 파싱 실패 또는 dry-run")
            failed += 1

    print(f"\n완료: {success}개 성공, {failed}개 실패 (총 {len(records)}개)")
    conn.close()


if __name__ == "__main__":
    main()
