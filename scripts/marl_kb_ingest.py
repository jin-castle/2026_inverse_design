#!/usr/bin/env python3
"""
marl_kb_ingest.py
-----------------
MARL(marl_orchestrator.py) 실행 완료 후 fix_history 를
Knowledge Base API 에 자동 저장하는 standalone 루틴.

주요 함수
  ingest_fix_to_kb(fix_item, project_id, meep_version) -> dict
  ingest_run_result(result, project_id)               -> list[dict]

API 엔드포인트 : http://localhost:8765/api/ingest/sim_error
인증           : X-Ingest-Key 헤더
설정           : /mnt/c/Users/user/projects/meep-kb/.env  (INGEST_API_KEY=...)
"""

import os
import json
import requests
from pathlib import Path

# ── 상수 ──────────────────────────────────────────────────────────────────────
KB_API      = "http://localhost:8765"
ENV_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/.env")
_TIMEOUT    = 10          # 초


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────
def _load_ingest_key() -> str:
    """
    .env 파일에서 INGEST_API_KEY 를 읽어 반환.
    파일이 없으면 환경변수 INGEST_API_KEY 를 fallback 으로 사용.
    """
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("INGEST_API_KEY") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("INGEST_API_KEY", "")


def _guess_error_type(error_msg: str) -> str:
    """error_message 문자열에서 에러 유형을 추론."""
    msg = (error_msg or "").lower()
    if "typeerror"       in msg: return "TypeError"
    if "attributeerror"  in msg: return "AttributeError"
    if "valueerror"      in msg: return "ValueError"
    if "importerror"     in msg: return "ImportError"
    if "mpi"             in msg: return "MPIError"
    if "nan"             in msg: return "NumericalDivergence"
    if "diverge"         in msg: return "Divergence"
    if "eigenmode"       in msg: return "EigenmodeError"
    if "pml"             in msg: return "PMLError"
    return "UnknownError"


# 모듈 로드 시점에 1회만 키를 읽음
_INGEST_KEY: str = _load_ingest_key()


# ── 공개 API ──────────────────────────────────────────────────────────────────
def ingest_fix_to_kb(
    fix_item: dict,
    project_id: str,
    meep_version: str = "1.31.0",
) -> dict:
    """
    fix_item 하나를 KB /api/ingest/sim_error 에 POST.

    fix_item 예상 키:
        attempt         int   - 시도 번호
        error_type      str   - 에러 타입 (없으면 error_message 에서 추론)
        error_message   str   - 에러 전문
        original_code   str   - 수정 전 코드
        fixed_code      str   - 수정 후 코드
        fix_description str   - 수정 설명
        kb_suggestion   str   - KB 에서 가져온 제안 (root_cause 로 전달)
        fix_worked      int   - 1=성공, 0=실패

    반환: {"ok": bool, "id": str|None, "message": str}
    실패 시 예외 없이 {"ok": False, "error": "..."} 반환.
    """
    error_msg   = fix_item.get("error_message", "")
    error_type  = fix_item.get("error_type") or _guess_error_type(error_msg)
    fix_worked  = int(fix_item.get("fix_worked", 0))

    payload = {
        "error_type":       error_type[:100],
        "error_message":    error_msg[:2000],
        "original_code":    fix_item.get("original_code", "")[:5000],
        "fixed_code":       fix_item.get("fixed_code",    "")[:5000],
        "fix_description":  fix_item.get("fix_description", "")[:1000],
        "root_cause":       fix_item.get("kb_suggestion", "")[:300],
        "fix_worked":       fix_worked,
        "project_id":       project_id,
        "meep_version":     meep_version,
        "context":          f"attempt={fix_item.get('attempt', 0)}",
        "source":           "marl_auto",
        "fix_keywords":     "[]",
        "pattern_name":     "",
    }

    headers = {"Content-Type": "application/json"}
    if _INGEST_KEY:
        headers["X-Ingest-Key"] = _INGEST_KEY

    try:
        resp = requests.post(
            f"{KB_API}/api/ingest/sim_error",
            json=payload,
            headers=headers,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # API 응답을 정규화해서 반환
        return {
            "ok":      data.get("ok", True),
            "id":      data.get("id") or data.get("run_id"),
            "message": data.get("message", "ingested"),
        }
    except requests.exceptions.HTTPError as e:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text[:300]
        return {"ok": False, "error": f"HTTP {resp.status_code}: {detail}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ingest_run_result(result: dict, project_id: str) -> list:
    """
    marl_orchestrator.run() 반환 dict 전체를 받아
    fix_history 를 순회하며 KB 에 저장.

    result 기대 구조:
        status      : "success" | "fixed" | "failed" | "blocked"
        fix_history : list[dict]   (각 항목은 ingest_fix_to_kb 참조)
        project_id  : str (result 에 있으면 project_id 인자보다 우선)

    fix_worked 결정 규칙:
        result['status'] in {"success", "fixed"}  -> 1
        그 외 (failed, blocked …)                 -> 0
        단, fix_history 항목 자체에 fix_worked 가 있으면 그 값을 우선.

    반환: [{"attempt": int, "ingest": {ok, id, message}}, ...]
    """
    fix_history  = result.get("fix_history", [])
    # result 에 project_id 가 있으면 우선 사용
    effective_pid = result.get("project_id") or project_id
    status        = result.get("status", "")
    run_level_worked = 1 if status in ("success", "fixed") else 0

    outputs = []
    for item in fix_history:
        # 항목 자체의 fix_worked 가 명시돼 있으면 그것을 사용,
        # 없으면 run-level status 로 결정
        if "fix_worked" in item:
            item_fw = int(bool(item["fix_worked"]))
        else:
            item_fw = run_level_worked

        # 작업 복사본에 fix_worked 를 주입
        enriched = dict(item)
        enriched["fix_worked"] = item_fw

        ingest_result = ingest_fix_to_kb(enriched, effective_pid)
        attempt_no    = item.get("attempt", "?")

        print(
            f"  [ingest] attempt={attempt_no}"
            f" fix_worked={item_fw}"
            f" -> ok={ingest_result.get('ok')}"
            f" id={ingest_result.get('id')}"
        )

        outputs.append({"attempt": attempt_no, "ingest": ingest_result})

    return outputs


# ── __main__ 테스트 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import subprocess

    print("=" * 60)
    print("marl_kb_ingest.py  셀프 테스트")
    print("=" * 60)

    # 1) KB API 상태 확인
    print("\n[1] KB API 상태 확인 (http://localhost:8765/api/status)")
    try:
        # requests 로 직접 확인 (subprocess curl 은 WSL 경로 이슈 회피)
        status_resp = requests.get(
            f"{KB_API}/api/status", timeout=5,
        )
        print("   ", status_resp.text.strip())
    except Exception as e:
        # fallback: subprocess curl
        try:
            proc = subprocess.run(
                ["/usr/bin/curl", "-s", "--max-time", "3",
                 "http://localhost:8765/api/status"],
                capture_output=True, text=True, timeout=5,
            )
            print("   ", proc.stdout.strip() or "(응답 없음)")
        except Exception as e2:
            print(f"    API 확인 실패: {e} / {e2}")

    # 2) INGEST_API_KEY 로드 확인
    print(f"\n[2] INGEST_API_KEY 로드: {'OK (' + _INGEST_KEY[:6] + '...)' if _INGEST_KEY else 'NOT FOUND'}")

    # 3) 더미 fix_item 단건 ingest 테스트
    print("\n[3] ingest_fix_to_kb() 단건 테스트")
    dummy_fix = {
        "attempt":         1,
        "error_type":      "TypeError",
        "error_message":   "TypeError: DiffractedPlanewave() got an unexpected keyword argument 'theta'",
        "original_code":   "src = mp.DiffractedPlanewave(theta=30)",
        "fixed_code":      "src = mp.DiffractedPlanewave(angle=30)",
        "fix_description": "theta -> angle 파라미터명 수정 (meep 1.31 API 변경)",
        "kb_suggestion":   "DiffractedPlanewave 경사각은 'angle' 파라미터로 전달해야 함",
        "fix_worked":      1,
    }
    r = ingest_fix_to_kb(dummy_fix, project_id="TEST-marl-ingest", meep_version="1.31.0")
    print("    결과:", json.dumps(r, ensure_ascii=False, indent=4))

    # 4) ingest_run_result() 전체 흐름 테스트
    print("\n[4] ingest_run_result() 전체 흐름 테스트")
    dummy_run = {
        "status":     "fixed",
        "project_id": "TEST-marl-run",
        "fix_history": [
            {
                "attempt":         1,
                "error_type":      "AttributeError",
                "error_message":   "AttributeError: 'Simulation' object has no attribute 'run_sources'",
                "original_code":   "sim.run_sources(mp.after_sources(mp.Harminv(...)))",
                "fixed_code":      "sim.run(mp.after_sources(mp.Harminv(...)))",
                "fix_description": "run_sources -> run 으로 API 변경",
                "kb_suggestion":   "meep >= 1.28 에서 run_sources 제거됨",
                # fix_worked 없음 → run-level status "fixed" 에서 1 로 결정
            },
            {
                "attempt":         2,
                "error_type":      "TypeError",
                "error_message":   "TypeError: invalid flux region",
                "original_code":   "mp.FluxRegion(center=mp.Vector3(1,0))",
                "fixed_code":      "mp.FluxRegion(center=mp.Vector3(1,0), size=mp.Vector3(0,1))",
                "fix_description": "FluxRegion size 누락 수정",
                "kb_suggestion":   "FluxRegion 에 size 인자 필수",
                "fix_worked":      1,
            },
        ],
    }
    results = ingest_run_result(dummy_run, project_id="FALLBACK-PID")
    print("\n    전체 결과:")
    print(json.dumps(results, ensure_ascii=False, indent=4))

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)
