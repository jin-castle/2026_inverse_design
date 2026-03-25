#!/usr/bin/env python3
"""
MEEP concepts 테이블 + FTS5 가상 테이블 생성
Usage: python -X utf8 tools/setup_concepts.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

CREATE_CONCEPTS = """
CREATE TABLE IF NOT EXISTS concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 개념 기본 정보
    name TEXT UNIQUE,           -- "PML", "EigenmodeSource", "FluxRegion" 등
    name_ko TEXT,               -- "완전 흡수 경계 조건", "고유모드 소스"
    aliases TEXT,               -- JSON array: ["perfectly matched layer", "pml"]
    category TEXT,              -- "boundary" | "source" | "monitor" | "geometry" | "optimization" | "analysis" | "simulation"
    difficulty TEXT,            -- "basic" | "intermediate" | "advanced"

    -- 개념 설명 (LLM 생성)
    summary TEXT,               -- 1~2문장 핵심 요약
    explanation TEXT,           -- 상세 설명 (물리 수식 포함, 한국어, 마크다운)
    physics_background TEXT,    -- 물리/수학 배경 설명
    common_mistakes TEXT,       -- 자주 하는 실수 (JSON array)
    related_concepts TEXT,      -- 연관 개념 (JSON array): ["PML", "resolution"]

    -- 데모 코드
    demo_code TEXT,             -- 독립 실행 가능한 최소 예제 코드
    demo_description TEXT,      -- 코드가 보여주는 것 설명

    -- 실행 결과 (Docker 실행 후 채울 예정)
    result_stdout TEXT,         -- 실행 출력
    result_images TEXT,         -- JSON array of base64 PNG
    result_executed_at TEXT,    -- 실행 시각
    result_status TEXT DEFAULT 'pending',  -- "pending" | "success" | "failed"

    -- 메타
    meep_version TEXT DEFAULT '1.31.0',
    doc_url TEXT,               -- MEEP 공식 문서 URL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CONCEPT_IDX_NAME = """
CREATE INDEX IF NOT EXISTS idx_concept_name ON concepts(name);
"""

CREATE_CONCEPT_IDX_CAT = """
CREATE INDEX IF NOT EXISTS idx_concept_category ON concepts(category);
"""

CREATE_CONCEPTS_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS concepts_fts USING fts5(
    name, name_ko, aliases, summary, explanation,
    content='concepts', content_rowid='id'
);
"""

# FTS 자동 동기화 트리거
CREATE_FTS_TRIGGER_INSERT = """
CREATE TRIGGER IF NOT EXISTS concepts_ai AFTER INSERT ON concepts BEGIN
    INSERT INTO concepts_fts(rowid, name, name_ko, aliases, summary, explanation)
    VALUES (new.id, new.name, new.name_ko, new.aliases, new.summary, new.explanation);
END;
"""

CREATE_FTS_TRIGGER_DELETE = """
CREATE TRIGGER IF NOT EXISTS concepts_ad AFTER DELETE ON concepts BEGIN
    INSERT INTO concepts_fts(concepts_fts, rowid, name, name_ko, aliases, summary, explanation)
    VALUES ('delete', old.id, old.name, old.name_ko, old.aliases, old.summary, old.explanation);
END;
"""

CREATE_FTS_TRIGGER_UPDATE = """
CREATE TRIGGER IF NOT EXISTS concepts_au AFTER UPDATE ON concepts BEGIN
    INSERT INTO concepts_fts(concepts_fts, rowid, name, name_ko, aliases, summary, explanation)
    VALUES ('delete', old.id, old.name, old.name_ko, old.aliases, old.summary, old.explanation);
    INSERT INTO concepts_fts(rowid, name, name_ko, aliases, summary, explanation)
    VALUES (new.id, new.name, new.name_ko, new.aliases, new.summary, new.explanation);
END;
"""


def setup():
    print(f"[setup_concepts] DB: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        conn.execute(CREATE_CONCEPTS)
        conn.execute(CREATE_CONCEPT_IDX_NAME)
        conn.execute(CREATE_CONCEPT_IDX_CAT)
        conn.execute(CREATE_CONCEPTS_FTS)
        conn.execute(CREATE_FTS_TRIGGER_INSERT)
        conn.execute(CREATE_FTS_TRIGGER_DELETE)
        conn.execute(CREATE_FTS_TRIGGER_UPDATE)
        conn.commit()
        print("[setup_concepts] OK concepts 테이블 생성 완료")
        print("[setup_concepts] OK concepts_fts 가상 테이블 생성 완료")
        print("[setup_concepts] OK FTS 자동 동기화 트리거 생성 완료")

        # 검증
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' OR type='shadow'").fetchall()]
        vtables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'concepts%'").fetchall()]
        print(f"[setup_concepts] concepts 관련 테이블: {vtables}")

        count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
        print(f"[setup_concepts] 현재 concepts 행 수: {count}")
    finally:
        conn.close()


if __name__ == "__main__":
    setup()
