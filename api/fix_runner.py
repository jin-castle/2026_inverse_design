"""
fix_runner.py — MEEP 수정 코드 실행 검증 모듈
==============================================
수정된 코드를 Docker 컨테이너에서 안전하게 실행해 결과 반환.

안전 정책:
  - resolution → 10 강제 (빠른 검증)
  - until / run_time → 20 제한
  - maxeval → 1 (adjoint 최적화 1 iter)
  - 위험 패턴(os.system, rm -rf 등) 사전 차단
  - 타임아웃 60초 hard limit
"""

import re, os, subprocess, tempfile, time
from pathlib import Path

DOCKER_CONTAINER = os.environ.get("MEEP_DOCKER", "meep-pilot-worker")

# 실행 금지 패턴 (보안)
_BLOCK_PATTERNS = [
    r'\bos\.system\s*\(',
    r'\bsubprocess\.(run|Popen|call)\s*\(',
    r'\brm\s+-rf\b',
    r'\bshutil\.rmtree\b',
    r'\bopen\s*\([^)]+["\']w["\']\)',  # 파일 쓰기
    r'\b__import__\s*\(',
    r'\bexec\s*\(',
    r'\beval\s*\(',
]


def _is_safe_code(code: str) -> tuple[bool, str]:
    """실행 금지 패턴 검사. Returns (safe, reason)."""
    for pat in _BLOCK_PATTERNS:
        if re.search(pat, code):
            return False, f"차단 패턴 감지: {pat}"
    return True, ""


def _make_validation_safe(code: str) -> str:
    """
    검증용으로 코드를 경량화:
      - resolution → 10
      - until=N → until=20
      - maxeval=N → maxeval=1
      - stop_when_fields_decayed threshold → 1e-3 (빠른 종료)
    """
    # resolution 강제 축소
    code = re.sub(r'\bresolution\s*=\s*\d+', 'resolution = 10', code)
    # run until 축소
    code = re.sub(r'\buntil\s*=\s*[\d.]+', 'until = 20', code)
    # maxeval (nlopt) 축소
    code = re.sub(r'\bmaxeval\s*=\s*\d+', 'maxeval = 1', code)
    code = re.sub(r'set_maxeval\s*\(\s*\d+\s*\)', 'set_maxeval(1)', code)
    # decay threshold 완화 (빠른 종료)
    code = re.sub(
        r'stop_when_fields_decayed\s*\(\s*[\d.]+\s*,\s*[^,]+,\s*[^,]+,\s*[\d.e\-]+\s*\)',
        lambda m: re.sub(r'([\d.e\-]+)\s*\)$', '1e-3)', m.group(0)),
        code
    )
    return code


def run_fixed_code(fixed_code: str, timeout: int = 60) -> dict:
    """
    수정된 코드를 Docker 컨테이너에서 실행 검증.

    Args:
        fixed_code: 실행할 Python 코드 문자열
        timeout:    최대 실행 시간 (초)

    Returns:
        {
          "success":   bool,    # 에러 없이 완료 여부
          "stdout":    str,     # 표준 출력 (최대 3000자)
          "stderr":    str,     # 표준 에러 (최대 1000자)
          "exit_code": int,
          "elapsed_s": float,
          "safe_code": str,     # 실제 실행된 경량화 코드
          "blocked":   bool,    # 보안 차단 여부
        }
    """
    # 보안 검사
    safe, reason = _is_safe_code(fixed_code)
    if not safe:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"[BLOCKED] {reason}",
            "exit_code": -2,
            "elapsed_s": 0.0,
            "safe_code": "",
            "blocked": True,
        }

    # 경량화
    safe_code = _make_validation_safe(fixed_code)

    # 임시 파일에 저장
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="/tmp/meep_fix_val_"
    ) as f:
        f.write(safe_code)
        tmp_path = f.name

    t0 = time.time()
    try:
        # Docker 내부에 파일 복사 후 실행
        # 1. docker cp로 파일 전송
        cp_result = subprocess.run(
            ["docker", "cp", tmp_path, f"{DOCKER_CONTAINER}:{tmp_path}"],
            capture_output=True, text=True, timeout=10
        )
        if cp_result.returncode != 0:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"docker cp 실패: {cp_result.stderr}",
                "exit_code": -1,
                "elapsed_s": round(time.time() - t0, 2),
                "safe_code": safe_code,
                "blocked": False,
            }

        # 2. python3 실행
        exec_result = subprocess.run(
            ["docker", "exec", DOCKER_CONTAINER,
             "python3", tmp_path],
            capture_output=True, text=True, timeout=timeout + 5
        )

        elapsed = round(time.time() - t0, 2)
        stdout = exec_result.stdout[-3000:] if exec_result.stdout else ""
        stderr = exec_result.stderr[-1000:] if exec_result.stderr else ""

        # 성공 판단: exit_code=0 + 에러 패턴 없음
        has_error = bool(re.search(
            r'(Error|Traceback|diverged|NaN|Inf\b|FATAL)',
            stdout + stderr, re.IGNORECASE
        ))
        success = (exec_result.returncode == 0) and not has_error

        return {
            "success":   success,
            "stdout":    stdout,
            "stderr":    stderr,
            "exit_code": exec_result.returncode,
            "elapsed_s": elapsed,
            "safe_code": safe_code,
            "blocked":   False,
        }

    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - t0, 2)
        return {
            "success":   False,
            "stdout":    "",
            "stderr":    f"TIMEOUT ({timeout}s 초과)",
            "exit_code": -1,
            "elapsed_s": elapsed,
            "safe_code": safe_code,
            "blocked":   False,
        }
    except FileNotFoundError:
        return {
            "success":   False,
            "stdout":    "",
            "stderr":    f"Docker 컨테이너 '{DOCKER_CONTAINER}' 없음 또는 docker 명령 없음",
            "exit_code": -1,
            "elapsed_s": 0.0,
            "safe_code": safe_code,
            "blocked":   False,
        }
    except Exception as e:
        return {
            "success":   False,
            "stdout":    "",
            "stderr":    str(e),
            "exit_code": -1,
            "elapsed_s": round(time.time() - t0, 2),
            "safe_code": safe_code,
            "blocked":   False,
        }
    finally:
        try:
            os.unlink(tmp_path)
            # 컨테이너 내부 임시 파일도 정리
            subprocess.run(
                ["docker", "exec", DOCKER_CONTAINER, "rm", "-f", tmp_path],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
