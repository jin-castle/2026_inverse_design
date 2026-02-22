# TODO — MEEP-KB 구축

**날짜:** 2026-02-22

---

## ✅ 실행 전
- [x] 계획 Jin에게 제시
- [x] Jin 컨펌 (Token 없음, 독립 폴더, stanfordnqp 추가)
- [x] PLAN.md 작성
- [x] 폴더 구조 생성

---

## 🔄 실행 단계

- [ ] **Step 1** — DB 초기화 (`01_db_setup.py`)
- [ ] **Step 2** — MEEP 이슈 수집 (`02_fetch_meep_issues.py`)
  - [ ] MEEP issues (~3,000개, rate-limited)
  - [ ] MPB issues (~400개)
- [ ] **Step 3** — 연구자 코드 수집 (`03_fetch_researcher_repos.py`)
  - [ ] zlin-opt/meep-adjoint-3d
  - [ ] jonfanlab repos
  - [ ] fancompute (legume, ceviche, workshop-invdesign)
  - [ ] stanfordnqp (spins-b, maxwell-b)
  - [ ] smartalecH repos
- [ ] **Step 4** — 공식 문서 수집 (`04_fetch_official_docs.py`)
- [ ] **Step 5** — 로컬 로그 파싱 (`05_parse_local_logs.py`)
- [ ] **Step 6** — Skill 자동 생성 (`06_export_skill.py`)
- [ ] **Step 7** — 검색 CLI 완성 (`query/search.py`)

---

## 🏁 최종 체크리스트

- [ ] DB에 에러 레코드 100건 이상
- [ ] DB에 코드 예제 50건 이상
- [ ] `search.py "meep error"` 정상 동작
- [ ] `.claude/skills/meep-simulation/` 생성 완료
- [ ] Jin에게 결과 보고
