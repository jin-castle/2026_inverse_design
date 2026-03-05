# Agent 1 Task: MEEP 예제 한국어 해설 작성

## 목표
meep-kb DB의 이미지가 있는 23개 예제에 대해 **연구자 관점**의 한국어 해설을 작성하고,
DB의 `examples` 테이블에 저장한다.

## 환경
- meep-kb Docker 컨테이너: `meep-kb-meep-kb-1`
- DB: `/app/db/knowledge.db` (컨테이너 내부)
- 결과 이미지: `/app/db/results/example_{id}_*.png` → `/static/results/`로 서빙
- meep docs: https://meep.readthedocs.io/en/master/

## 작업 순서

### Step 1: DB 스키마 확장
```python
# examples 테이블에 description_ko 컬럼 추가
import sqlite3
conn = sqlite3.connect("knowledge.db")
conn.execute("ALTER TABLE examples ADD COLUMN description_ko TEXT")
conn.commit()
```

### Step 2: 예제 목록 확인
파일 `agent1_examples.json` 참조 — 23개 예제 id, title, code 포함

### Step 3: 각 예제별 해설 작성
각 예제에 대해 다음 구조로 한국어 해설을 작성:

```markdown
## [예제 제목]

### 물리적 배경
이 시뮬레이션이 모델링하는 물리 현상 설명 (파동 방정식, 경계조건 등)

### 시뮬레이션 세팅
- 셀 크기, PML, 해상도
- 재료 정의 (유전율, 분산 등)
- 소스 타입과 위치

### 핵심 MEEP 개념
- 사용된 주요 API (EigenModeSource, DFT 등)
- 모니터 설정과 데이터 추출 방법

### 결과 해석
- 생성된 이미지가 보여주는 것
- 물리적 의미

### 연구 활용
SOI 포토닉스 / 역설계 관점에서 이 예제의 활용 방법
```

### Step 4: DB 저장
```python
# 각 예제에 해설 저장
conn.execute("UPDATE examples SET description_ko=? WHERE id=?", (description, example_id))
```

### Step 5: dict_page.py 업데이트
`C:\Users\user\projects\meep-kb\api\dict_page.py` 의 Examples 탭에서:
- 예제 카드 클릭 시 해설(description_ko) 표시
- `<details>` 토글로 표시
- docker cp + restart로 배포

## 참고 meep docs URLs (주요 섹션)
- https://meep.readthedocs.io/en/master/Introduction/
- https://meep.readthedocs.io/en/master/Exploiting_Symmetry/
- https://meep.readthedocs.io/en/master/Mode_Decomposition/
- https://meep.readthedocs.io/en/master/Python_Tutorials/Basics/
- https://meep.readthedocs.io/en/master/Python_Tutorials/Eigenmode_Source/
- https://meep.readthedocs.io/en/master/Python_Tutorials/Local_Density_of_States/
- https://meep.readthedocs.io/en/master/Python_Tutorials/Near_to_Far_Field_Spectra/

## 완료 후 알림
완료되면 다음 명령 실행:
```
openclaw system event --text "Agent1 완료: MEEP 예제 23개 한국어 해설 작성 완료 + dict_page.py 배포" --mode now
```
