"""현재 시스템 구성 + agent 관점 gap 분석"""
import os, re, json
from pathlib import Path

BASE = Path('C:/Users/user/projects/meep-kb/cis_repro')

# 파일 목록 + 의존관계
files = []
for f in sorted(BASE.rglob('*.py')):
    if '__pycache__' in str(f): continue
    try:
        code = f.read_text(encoding='utf-8', errors='replace')
        rel  = str(f.relative_to(BASE))
        imps = re.findall(r'(?:from|import)\s+([\w.]+)', code)
        files.append({'path': rel, 'lines': len(code.splitlines()), 'imports': imps, 'code': code})
    except: pass

print("=== 현재 구성 파일 ===")
for f in files:
    deps = [i for i in f['imports'] if any(k in i for k in
            ['detector','pipeline','extractor','generator','validator','runner','saver'])]
    print(f"  {f['path']:<45} {f['lines']:>4}줄  deps={deps}")

# 각 stage별 구현 완성도 체크
print("\n=== Stage별 구현 현황 ===")
stages = {
    "Stage 0A (PDF→params)":      "stage0/param_extractor.py",
    "Stage 0B (입력 분류 A/B/C)": "pipeline.py",
    "Stage 0C (Mode B KB 적용)":  None,
    "Stage 0D (Mode C adjoint)":  None,
    "Stage 1 (코드 생성)":         "pipeline.py",
    "Stage 1 (Jinja2 템플릿)":    "templates/base_cis_cell.py.j2",
    "Stage 2 (구조 유사도)":       None,
    "Stage 3 (실행 환경 결정)":    "pipeline.py",
    "Stage 3 (Docker 실행)":      "pipeline.py",
    "Stage 3 (SimServer 실행)":   "pipeline.py",
    "Stage 3E (오류 탐지)":       "detector.py",
    "Stage 3E (자동 수정)":       "detector.py",
    "Stage 4 (결과 검증 ≤5%)":   "pipeline.py",
    "Stage 4 (meep-kb 저장)":    "pipeline.py",
    "암묵지 문서":                  "CIS_TACIT_KNOWLEDGE.md",
    "오류 규칙 DB":                 "error_rules.json",
}
for stage, fpath in stages.items():
    if fpath:
        exists = (BASE / fpath).exists()
        status = "OK" if exists else "MISSING"
    else:
        status = "NOT IMPL"
    print(f"  {stage:<35} [{status}]")

# pipeline.py에서 실제 연결 확인
print("\n=== pipeline.py 내부 연결 확인 ===")
pipe = (BASE / 'pipeline.py').read_text(encoding='utf-8', errors='replace')
checks = {
    "detector.py import": "from detector import" in pipe or "import detector" in pipe,
    "param_extractor import": "param_extractor" in pipe,
    "Jinja2 템플릿 사용": "jinja2" in pipe.lower() or "j2" in pipe,
    "error_rules.json 로드": "error_rules" in pipe,
    "meep-kb DB 저장": "INSERT INTO examples" in pipe,
    "SimServer SSH": "SIMSERVER" in pipe,
    "Docker 실행": "docker exec" in pipe,
    "fast-check": "fast_check" in pipe or "fast-check" in pipe,
    "구조 유사도": "structure_validator" in pipe or "structure_match" in pipe,
    "≤5% 오차 검증": "validate_result" in pipe or "5.0" in pipe,
}
for item, ok in checks.items():
    status = "OK" if ok else "MISSING"
    print(f"  {item:<35} [{status}]")
