# -*- coding: utf-8 -*-
"""
live_runner.py — Phase 2: Docker MEEP 실행기
=============================================
meep-pilot-worker 컨테이너에서 코드를 격리 실행하고 결과를 반환.

사용:
  from tools.live_runner import run_code
  result = run_code(code, timeout=120)
"""
import re, os, subprocess, time, uuid, tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import sys

# diagnose_engine 경로 등록
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
from diagnose_engine import check_mpi_deadlock_risk, parse_error

CONTAINER = "meep-pilot-worker"
CONTAINER_WORKSPACE = "/workspace"

# ──────────────────────────────────────────────────────────────────────────────
# 결과 데이터클래스
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    status: str          # success | error | timeout | mpi_deadlock_risk | blocked
    stdout: str = ""
    stderr: str = ""
    run_time_sec: float = 0.0
    error_type: str = ""
    error_message: str = ""
    T_value: Optional[float] = None
    R_value: Optional[float] = None
    mpi_check: dict = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# 보안 차단 패턴
# ──────────────────────────────────────────────────────────────────────────────

BLOCKED_PATTERNS = [
    (r'\bsubprocess\b', "subprocess 사용 차단"),
    (r'\bshutil\.rmtree\b', "shutil.rmtree 사용 차단"),
    (r'\bos\.system\s*\(', "os.system 사용 차단"),
    (r'\bos\.remove\s*\(', "os.remove 사용 차단"),
    (r'\bos\.unlink\s*\(', "os.unlink 사용 차단"),
    (r'\beval\s*\(', "eval 사용 차단"),
    (r'\bexec\s*\(', "exec 사용 차단"),
    (r'\b__import__\s*\(', "__import__ 사용 차단"),
    (r'open\s*\([^)]*["\'][wa]["\']', "파일 쓰기(non-meep) 차단"),
]

def security_check(code: str) -> Optional[str]:
    """보안 위반 패턴 검사. 위반 시 사유 문자열 반환, 통과 시 None"""
    for pattern, reason in BLOCKED_PATTERNS:
        # open(..., 'w') 은 meep output 파일은 허용 (h5, png 등 제외하고 차단)
        if pattern == r'open\s*\([^)]*["\'][wa]["\']':
            if re.search(pattern, code):
                # meep 관련 출력이면 허용 (h5py, numpy 저장 등은 별도)
                if not re.search(r'mp\.|meep\.', code[:50]):
                    # 코드 전체적으로 meep 사용 여부 확인
                    if re.search(r'\bimport meep\b', code):
                        continue  # meep 코드에서의 파일 쓰기는 허용
                    return reason
        elif re.search(pattern, code):
            return reason
    return None


# ──────────────────────────────────────────────────────────────────────────────
# 출력 파싱
# ──────────────────────────────────────────────────────────────────────────────

def parse_tr_values(output: str) -> tuple[Optional[float], Optional[float]]:
    """stdout에서 T/R 값 추출. [RESULT] T = ... R = ... 패턴"""
    T_val = None
    R_val = None

    # [RESULT] T = 0.1234 패턴
    m = re.search(r'\[RESULT\]\s+T\s*=\s*([-\d.eE+]+)', output)
    if m:
        try: T_val = float(m.group(1))
        except: pass

    m = re.search(r'\[RESULT\]\s+R\s*=\s*([-\d.eE+]+)', output)
    if m:
        try: R_val = float(m.group(1))
        except: pass

    # T = 0.xxxx 패턴 (더 넓게)
    if T_val is None:
        m = re.search(r'T\s*=\s*([-\d.eE+]+)', output)
        if m:
            try: T_val = float(m.group(1))
            except: pass

    if R_val is None:
        m = re.search(r'R\s*=\s*([-\d.eE+]+)', output)
        if m:
            try: R_val = float(m.group(1))
            except: pass

    return T_val, R_val


def extract_error_info(stderr: str, stdout: str) -> tuple[str, str]:
    """stderr/stdout에서 에러 타입과 메시지 추출"""
    combined = stderr + "\n" + stdout
    lines = combined.strip().splitlines()

    # 마지막 에러 라인 탐색
    error_line = ""
    for line in reversed(lines):
        stripped = line.strip()
        if re.match(r'^(\w+Error|\w+Exception|meep\.|Traceback|Error:)', stripped):
            error_line = stripped
            break

    # diagnose_engine parse_error 활용
    error_info = parse_error("", combined)
    error_type = error_info.get("primary_type", "Unknown")

    if not error_line and error_info.get("last_error_line"):
        error_line = error_info["last_error_line"]

    return error_type, error_line[:500]


# ──────────────────────────────────────────────────────────────────────────────
# 컨테이너 존재 확인
# ──────────────────────────────────────────────────────────────────────────────

def check_container() -> bool:
    """meep-pilot-worker 컨테이너가 실행 중인지 확인"""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# 메인 실행 함수
# ──────────────────────────────────────────────────────────────────────────────

def run_code(code: str, timeout: int = 120) -> RunResult:
    """
    MEEP 코드를 meep-pilot-worker 컨테이너에서 격리 실행.

    Args:
        code: 실행할 Python/MEEP 코드
        timeout: 최대 실행 시간 (초, 기본 120)

    Returns:
        RunResult dataclass
    """
    # 1. 보안 체크
    block_reason = security_check(code)
    if block_reason:
        return RunResult(
            status="blocked",
            stderr=f"[SECURITY BLOCKED] {block_reason}",
            error_type="SecurityBlock",
            error_message=block_reason,
        )

    # 2. MPI deadlock 사전 검토
    mpi_check = check_mpi_deadlock_risk(code)
    if mpi_check.get("risk_level") == "high":
        return RunResult(
            status="mpi_deadlock_risk",
            stderr=f"[MPI DEADLOCK RISK] {mpi_check.get('issues', [])}",
            error_type="MPIDeadlockRisk",
            error_message=str(mpi_check.get("issues", []))[:300],
            mpi_check=mpi_check,
        )

    # 3. 컨테이너 확인
    if not check_container():
        return RunResult(
            status="error",
            stderr=f"[CONTAINER ERROR] {CONTAINER} 컨테이너가 실행 중이지 않습니다.",
            error_type="ContainerError",
            error_message=f"Container {CONTAINER} is not running",
        )

    # 4. 임시 파일 생성 및 컨테이너로 복사
    run_id = str(uuid.uuid4()).replace("-", "")[:12]
    container_dir = f"{CONTAINER_WORKSPACE}/live_{run_id}"
    container_script = f"{container_dir}/script.py"

    tmp_path = None
    try:
        # 임시 파일에 코드 저장
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(code)
            tmp_path = f.name

        # 컨테이너 내 디렉토리 생성
        subprocess.run(
            ["docker", "exec", CONTAINER, "mkdir", "-p", container_dir],
            capture_output=True, timeout=10
        )

        # 파일 복사
        cp_result = subprocess.run(
            ["docker", "cp", tmp_path, f"{CONTAINER}:{container_script}"],
            capture_output=True, text=True, timeout=15
        )
        if cp_result.returncode != 0:
            return RunResult(
                status="error",
                stderr=f"[DOCKER CP ERROR] {cp_result.stderr}",
                error_type="DockerError",
                error_message=cp_result.stderr[:300],
            )

        # 5. 컨테이너에서 실행
        start_time = time.time()
        try:
            exec_result = subprocess.run(
                ["docker", "exec", CONTAINER, "python", container_script],
                capture_output=True, text=True,
                timeout=timeout,
                encoding="utf-8", errors="replace"
            )
            run_time = time.time() - start_time

            stdout = exec_result.stdout or ""
            stderr = exec_result.stderr or ""

            # T/R 값 파싱
            T_val, R_val = parse_tr_values(stdout)

            if exec_result.returncode == 0:
                status = "success"
                error_type = ""
                error_msg = ""
            else:
                status = "error"
                error_type, error_msg = extract_error_info(stderr, stdout)

            return RunResult(
                status=status,
                stdout=stdout[:5000],
                stderr=stderr[:3000],
                run_time_sec=round(run_time, 2),
                error_type=error_type,
                error_message=error_msg,
                T_value=T_val,
                R_value=R_val,
                mpi_check=mpi_check,
            )

        except subprocess.TimeoutExpired:
            run_time = time.time() - start_time
            return RunResult(
                status="timeout",
                stderr=f"[TIMEOUT] {timeout}초 초과",
                run_time_sec=round(run_time, 2),
                error_type="Timeout",
                error_message=f"Execution exceeded {timeout} seconds",
                mpi_check=mpi_check,
            )

    except Exception as e:
        return RunResult(
            status="error",
            stderr=str(e),
            error_type="RunnerError",
            error_message=str(e)[:300],
        )

    finally:
        # 임시 파일 정리
        if tmp_path:
            try: os.unlink(tmp_path)
            except: pass
        # 컨테이너 내 디렉토리 정리
        try:
            subprocess.run(
                ["docker", "exec", CONTAINER, "rm", "-rf", container_dir],
                capture_output=True, timeout=10
            )
        except: pass


# ──────────────────────────────────────────────────────────────────────────────
# CLI (간단한 테스트)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MEEP 코드 실행기")
    parser.add_argument("--file", type=str, help="실행할 .py 파일 경로")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    if args.file:
        code = Path(args.file).read_text(encoding="utf-8")
    else:
        code = """
import meep as mp
resolution = 10
cell = mp.Vector3(16, 0, 0)
sim = mp.Simulation(cell_size=cell, resolution=resolution)
print("[RESULT] T = 0.9999")
"""

    print(f"컨테이너 실행 중: {check_container()}")
    result = run_code(code, timeout=args.timeout)
    print(f"Status: {result.status}")
    print(f"Run time: {result.run_time_sec}s")
    if result.T_value is not None:
        print(f"T = {result.T_value}")
    if result.error_type:
        print(f"Error type: {result.error_type}")
    if result.stderr:
        print(f"stderr: {result.stderr[:300]}")
