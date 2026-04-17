# KB Regression Test Cases

## 개요

`gen_regression_cases.py`가 `sim_errors_v2` 테이블(fix_worked=1, 상위 20건)에서
자동 생성한 회귀 테스트 케이스 파일들입니다.

## 파일 구조

각 케이스는 두 파일로 구성됩니다:

| 파일 | 설명 |
|------|------|
| `case_NNN_input.md`    | 사용자가 실제로 할 법한 에러 호소 텍스트 (검색 쿼리로 사용) |
| `case_NNN_expected.yaml` | 예상 검색 결과 ID, 금지 ID, 허용 추가 ID, 검증 기준 |

## 생성된 케이스 목록

- case_001_input.md / case_001_expected.yaml
- case_002_input.md / case_002_expected.yaml
- case_003_input.md / case_003_expected.yaml
- case_004_input.md / case_004_expected.yaml
- case_005_input.md / case_005_expected.yaml
- case_006_input.md / case_006_expected.yaml
- case_008_input.md / case_008_expected.yaml
- case_009_input.md / case_009_expected.yaml
- case_011_input.md / case_011_expected.yaml
- case_012_input.md / case_012_expected.yaml
- case_013_input.md / case_013_expected.yaml
- case_014_input.md / case_014_expected.yaml
- case_016_input.md / case_016_expected.yaml
- case_017_input.md / case_017_expected.yaml
- case_018_input.md / case_018_expected.yaml
- case_019_input.md / case_019_expected.yaml
- case_020_input.md / case_020_expected.yaml
- case_021_input.md / case_021_expected.yaml
- case_024_input.md / case_024_expected.yaml
- case_025_input.md / case_025_expected.yaml

## 회귀 테스트 실행

```bash
python3 tests/kb_regression/run_regression.py
python3 tests/kb_regression/run_regression.py --verbose
```

## 결과 해석

- **top-1 hit rate**: 검색 결과 1위가 정답인 비율
- **top-3 hit rate**: 상위 3개 결과 안에 정답이 포함된 비율

hit 판정 조건:
1. 결과 title에 `sim_v2_{id}` 패턴이 포함되거나
2. 결과 title/category에 `hit_keywords` 키워드가 매칭될 때

## 파일 재생성

```bash
python3 tests/kb_regression/gen_regression_cases.py
```

DB 변경 후 재실행하면 케이스 파일들이 갱신됩니다.
