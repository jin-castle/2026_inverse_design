# PLAN — MEEP/FDTD 지식 데이터베이스 시스템

**날짜:** 2026-02-22  
**상태:** `Confirmed — In Progress`  
**위치:** `C:\Users\user\projects\meep-kb\`

---

## 🎯 목표

MEEP / MPB / legume 관련 작업 시 포비가 즉시 참조할 수 있는 **통합 지식 DB** 구축.  
공식 문서 · 유명 연구자 코드 · GitHub 커뮤니티 에러 전수 수집 → SQLite DB화.

---

## 🗂️ 데이터 소스

### 공식 문서 & 레포
| 소스 | URL |
|------|-----|
| MEEP docs | https://meep.readthedocs.io |
| MPB docs | https://mpb.readthedocs.io |
| MEEP GitHub | https://github.com/NanoComp/meep |
| MPB GitHub | https://github.com/NanoComp/mpb |

### 유명 연구자 GitHub
| 그룹 | GitHub | 주요 내용 |
|------|--------|----------|
| Zin Lin (MIT) | github.com/zlin-opt | meep-adjoint-3d, RCWA |
| Jonathan Fan (Stanford) | github.com/jonfanlab | nanophotonics FDTD |
| Fan Group (Stanford) | github.com/fancompute | legume, ceviche, workshop-invdesign |
| Jelena Vučković (Stanford) | github.com/stanfordnqp | SPINS-b (photonic opt), maxwell-b |
| Alec Hammond (MEEP contrib) | github.com/smartalecH | adjoint MEEP |
| Steven Johnson (MIT) | github.com/NanoComp | MEEP 핵심 개발자 |

### MEEP 커뮤니티 (핵심)
| 소스 | 예상 규모 |
|------|----------|
| github.com/NanoComp/meep/issues (all) | ~3,000개 |
| github.com/NanoComp/mpb/issues (all) | ~400개 |

### 로컬 데이터
| 소스 | 내용 |
|------|------|
| /root/cfwdm/*.log (15개) | Jin 실험 에러 기록 |
| photonics-agent/db/knowledge.db | 기존 MEEP 패턴 10건 |

---

## 🗄️ DB 스키마

```sql
-- 에러 & 해결책 (핵심)
errors(id, error_msg, category, cause, solution, source_url, source_type, verified, created_at)

-- 코드 예제
examples(id, title, code, description, tags, source_repo, author, file_path, created_at)

-- 문서 청크
docs(id, section, content, url, simulator, created_at)

-- 연구자 패턴
patterns(id, pattern_name, description, code_snippet, use_case, author_repo, created_at)
```

---

## 📋 실행 단계

| # | 스크립트 | 내용 |
|---|---------|------|
| 1 | `01_db_setup.py` | DB 초기화, 스키마 생성 |
| 2 | `02_fetch_meep_issues.py` | MEEP/MPB GitHub 이슈 전수 수집 |
| 3 | `03_fetch_researcher_repos.py` | 연구자 repo 예제 코드 수집 |
| 4 | `04_fetch_official_docs.py` | readthedocs 핵심 페이지 수집 |
| 5 | `05_parse_local_logs.py` | cfwdm 로그 파싱 + KB 마이그레이션 |
| 6 | `06_export_skill.py` | DB → .claude/skills 자동 생성 |
| 7 | `search.py` | CLI 검색 인터페이스 완성 |

---

## 📦 예상 결과물

1. `db/knowledge.db` — 통합 지식 DB (SQLite)
2. `query/search.py` — `python search.py "Courant factor"` 즉시 답변
3. `.claude/skills/meep-simulation/resources/common-errors.md` — 자동 생성
4. `.claude/skills/meep-simulation/resources/code-patterns.md` — 자동 생성
