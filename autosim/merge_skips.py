"""
merge_skips.py
skip 패턴들의 result.json을 run_summary.json에 반영.
Docker 컨테이너 내에서 실행.
"""
import json
from pathlib import Path

RESULTS_DIR  = Path("/root/autosim/results")
SUMMARY_PATH = Path("/root/autosim/run_summary.json")

# 현재 summary 로드
data = json.loads(SUMMARY_PATH.read_text())
summary_map = {d["pattern"]: d for d in data}

# results/ 폴더에서 skip 상태인 것들 찾기
updated = 0
for result_dir in RESULTS_DIR.iterdir():
    result_file = result_dir / "result.json"
    if not result_file.exists():
        continue
    r = json.loads(result_file.read_text())
    if r.get("status") == "skip":
        name = r["pattern"]
        if name in summary_map:
            # 기존 error → skip으로 교체
            if summary_map[name]["status"] != "skip":
                summary_map[name] = r
                updated += 1
                print("[UPDATED] {} error->skip".format(name))
        else:
            # summary에 없으면 추가
            summary_map[name] = r
            updated += 1
            print("[ADDED] {} as skip".format(name))

# 저장
final = list(summary_map.values())
SUMMARY_PATH.write_text(json.dumps(final, indent=2, ensure_ascii=False))
print("\nrun_summary.json updated: {} changes".format(updated))

# 최종 통계
ok   = sum(1 for d in final if d["status"] == "ok")
err  = sum(1 for d in final if d["status"] == "error")
skip = sum(1 for d in final if d["status"] == "skip")
to   = sum(1 for d in final if d["status"] == "timeout")
print("Final: OK {} | ERR {} | SKIP {} | TIMEOUT {} | TOTAL {}".format(ok, err, skip, to, len(final)))
