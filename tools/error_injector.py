"""
ErrorInjector: autosim 정상 패턴에 의도적 버그 삽입
→ Docker MEEP 실행 → 실제 traceback 캡처 → sim_errors 저장

실행:
  python tools/error_injector.py --dry-run --limit 5
  python tools/error_injector.py --limit 20
"""
import re, json, os, subprocess, time, argparse, sqlite3, tempfile, shutil
from pathlib import Path

BASE = Path(__file__).parent.parent
PATTERNS_DIR = BASE / "autosim" / "patterns"
DB_PATH = BASE / "db" / "knowledge.db"
CONTAINER = "meep-pilot-worker"
KB_URL = "http://localhost:8765"

# ------------------------------------------------------------------
# 버그 카탈로그: (이름, 패턴 코드, 수정 설명, 적용 가능 조건)
# ------------------------------------------------------------------
BUG_CATALOG = [
    {
        "name": "eig_band_zero",
        "error_type": "EigenMode",
        "find": r'eig_band\s*=\s*1',
        "replace": "eig_band=0",
        "fix_description": "MEEP에서 eig_band는 1-indexed입니다. eig_band=0은 정의되지 않은 모드입니다. eig_band=1 (TE0), eig_band=2 (TE1)으로 수정하세요.",
        "root_cause": "eig_band=0: MEEP 모드 인덱스는 1부터 시작. 0을 쓰면 에너지 비보존(T>100%) 발생",
    },
    {
        "name": "no_pml",
        "error_type": "PML",
        "find": r'boundary_layers\s*=\s*\[.*?PML.*?\]',
        "replace": "boundary_layers=[]",
        "fix_description": "PML(Perfectly Matched Layer) 없이 시뮬레이션하면 경계에서 반사가 발생해 결과가 부정확합니다. boundary_layers=[mp.PML(1.0)]을 추가하세요.",
        "root_cause": "PML 없음: 경계 반사로 인한 부정확한 결과 및 발산 가능성",
    },
    {
        "name": "wrong_eig_parity",
        "error_type": "EigenMode",
        "find": r'eig_parity\s*=\s*mp\.EVEN_Y\s*\+\s*mp\.ODD_Z',
        "replace": "eig_parity=mp.ODD_Y+mp.EVEN_Z",
        "fix_description": "2D TE 모드에서 올바른 eig_parity는 mp.EVEN_Y+mp.ODD_Z입니다. ODD_Y+EVEN_Z는 TM 모드입니다.",
        "root_cause": "eig_parity 오류: TE/TM 모드 혼동으로 잘못된 모드 여기",
    },
    {
        "name": "resolution_too_low",
        "error_type": "General",
        "find": r'resolution\s*=\s*(\d+)',
        "replace": "resolution=2",
        "fix_description": "resolution=2는 너무 낮습니다. 최소 10 이상, 정확한 결과를 위해 50+ 권장. resolution을 올리면 정확도가 향상됩니다.",
        "root_cause": "resolution 너무 낮음: 격자가 너무 거칠어 수치 발산 또는 부정확한 결과",
    },
    {
        "name": "missing_until",
        "error_type": "RuntimeError",
        "find": r'sim\.run\(until\s*=\s*(\d+)',
        "replace": "sim.run(until=0.001",
        "fix_description": "until=0.001은 너무 짧아 필드가 수렴하지 않습니다. 충분한 시간(예: until=200)을 설정하거나 stop_when_fields_decayed()를 사용하세요.",
        "root_cause": "시뮬레이션 시간 너무 짧음: 필드가 수렴하기 전에 종료",
    },
    {
        "name": "force_complex_missing",
        "error_type": "ValueError",
        "find": r'force_complex_fields\s*=\s*True',
        "replace": "force_complex_fields=False",
        "fix_description": "EigenModeSource나 위상 관련 계산에서 force_complex_fields=True가 필요합니다. False로 설정하면 복소수 필드 접근 시 오류가 발생합니다.",
        "root_cause": "force_complex_fields=False: 복소수 모드 계수 계산에서 오류 발생",
    },
    {
        "name": "wrong_component",
        "error_type": "ValueError",
        "find": r'mp\.Ez',
        "replace": "mp.Ey",
        "fix_description": "2D TE 모드 시뮬레이션에서 올바른 필드 성분은 mp.Ez입니다. mp.Ey는 TM 모드에 해당합니다.",
        "root_cause": "잘못된 필드 성분: TE/TM 편광 혼동",
    },
    {
        "name": "pml_too_thin",
        "error_type": "PML",
        "find": r'mp\.PML\s*\(\s*[\d.]+\s*\)',
        "replace": "mp.PML(0.1)",
        "fix_description": "PML 두께 0.1은 너무 얇아 반사가 발생합니다. 파장의 절반 이상(λ/2 ≈ 0.775μm)을 권장하며, 일반적으로 1.0μm 이상 사용합니다.",
        "root_cause": "PML 너무 얇음: 불충분한 흡수로 경계 반사 발생",
    },
]


# ------------------------------------------------------------------
# 버그 주입
# ------------------------------------------------------------------

def inject_bug(original_code: str, bug: dict) -> str | None:
    """원본 코드에 버그 삽입. 적용 불가하면 None 반환"""
    pattern = bug["find"]
    replacement = bug["replace"]
    if re.search(pattern, original_code):
        new_code = re.sub(pattern, replacement, original_code, count=1)
        if new_code != original_code:
            return new_code
    return None


# ------------------------------------------------------------------
# Docker에서 실행
# ------------------------------------------------------------------

def run_in_docker(code: str, timeout: int = 30) -> tuple[int, str]:
    """코드를 Docker MEEP 컨테이너에서 실행. (returncode, output) 반환"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w",
                                     encoding="utf-8", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        container_path = f"/tmp/test_inject_{Path(tmp_path).name}"
        subprocess.run(
            ["docker", "cp", tmp_path, f"{CONTAINER}:{container_path}"],
            capture_output=True, timeout=10
        )
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "python", container_path],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        output = result.stdout + result.stderr
        subprocess.run(
            ["docker", "exec", CONTAINER, "rm", "-f", container_path],
            capture_output=True, timeout=5
        )
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "TimeoutError: 실행 시간 초과"
    except Exception as e:
        return 1, str(e)
    finally:
        try: os.unlink(tmp_path)
        except: pass


# ------------------------------------------------------------------
# 에러 파싱
# ------------------------------------------------------------------

def extract_error_message(output: str) -> str:
    """stdout+stderr에서 핵심 에러 메시지 추출"""
    lines = output.strip().splitlines()
    # Traceback 마지막 줄 우선
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if re.match(r'^(Error|Warning|meep:|Traceback|.*Error:)', line):
            # 전후 컨텍스트 포함
            start = max(0, i - 5)
            return "\n".join(lines[start:i+3])[:500]
    # 전체 출력 마지막 부분
    return "\n".join(lines[-10:])[:500]


# ------------------------------------------------------------------
# sim_errors 저장
# ------------------------------------------------------------------

def save_to_db(conn, pattern_name: str, bug: dict,
               error_message: str, original_code: str, full_output: str):
    """sim_errors에 저장"""
    import datetime
    conn.execute("""
        INSERT INTO sim_errors
          (run_id, project_id, error_type, error_message, meep_version,
           context, root_cause, fix_applied, fix_worked,
           fix_description, fix_keywords, pattern_name, source,
           original_code, fixed_code, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f"inject_{pattern_name}_{bug['name']}",
        "error_injector",
        bug["error_type"],
        error_message[:500],
        "",
        full_output[:500],
        bug["root_cause"],
        bug["fix_description"][:300],
        1,  # fix_worked=1 (원본 코드 = 수정본)
        bug["fix_description"],
        json.dumps([bug["name"], bug["error_type"]], ensure_ascii=False),
        f"{pattern_name}__{bug['name']}",
        "error_injector",
        error_message[:2000],  # original_code = 버그 있는 코드 (실제 에러 발생)
        original_code[:5000],  # fixed_code = 원본 (버그 없는 코드)
        datetime.datetime.now().isoformat(),
    ))
    conn.commit()


# ------------------------------------------------------------------
# 메인
# ------------------------------------------------------------------

def run(limit: int = 0, dry_run: bool = False):
    pattern_files = sorted(PATTERNS_DIR.glob("*.py"))
    if limit:
        pattern_files = pattern_files[:limit * 2]

    conn = sqlite3.connect(DB_PATH)

    # 이미 처리된 것 확인
    already = set()
    for row in conn.execute(
        "SELECT pattern_name FROM sim_errors WHERE source='error_injector'"
    ).fetchall():
        already.add(row[0])

    saved = 0
    tried = 0

    for pat_file in pattern_files:
        if limit and saved >= limit:
            break

        original_code = pat_file.read_text(encoding="utf-8", errors="replace")
        pat_name = pat_file.stem

        for bug in BUG_CATALOG:
            key = f"{pat_name}__{bug['name']}"
            if key in already:
                continue

            # 버그 삽입 가능한지 확인
            buggy_code = inject_bug(original_code, bug)
            if not buggy_code:
                continue

            tried += 1
            print(f"[{tried}] {pat_name} + {bug['name']}")

            if dry_run:
                print(f"  [DRY-RUN] 버그 삽입 가능: {bug['replace'][:50]}")
                continue

            # Docker에서 실행
            retcode, output = run_in_docker(buggy_code, timeout=25)

            if retcode == 0:
                # 버그 삽입해도 성공한 경우 (패턴과 버그가 안 맞음)
                print(f"  → 성공 (버그 효과 없음, 스킵)")
                continue

            error_msg = extract_error_message(output)
            print(f"  → 에러 캡처: {error_msg[:80]}")

            save_to_db(conn, pat_name, bug, error_msg, original_code, output)
            saved += 1
            print(f"  → sim_errors 저장 (total: {saved})")

            time.sleep(0.2)

    conn.close()

    if not dry_run:
        print(f"\n완료: {saved}개 저장")
        conn2 = sqlite3.connect(DB_PATH)
        total = conn2.execute("SELECT COUNT(*) FROM sim_errors").fetchone()[0]
        conn2.close()
        print(f"sim_errors 총 {total}개")
    else:
        print(f"\n[DRY-RUN] 주입 가능: {tried}개")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(args.limit, args.dry_run)
