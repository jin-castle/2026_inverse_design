"""
sim_errors 테이블 생성 + ChromaDB sim_errors_v1 컬렉션 초기화
"""
import sqlite3, os, json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sim_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_type TEXT NOT NULL,
    error_msg TEXT NOT NULL,
    error_context TEXT,
    original_code TEXT,
    fixed_code TEXT,
    fix_description TEXT,
    fix_keywords TEXT,       -- JSON array of strings
    pattern_name TEXT,
    source TEXT DEFAULT 'autosim',  -- 'autosim' | 'user_submitted' | 'github'
    verified BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_sim_errors_type ON sim_errors(error_type);",
    "CREATE INDEX IF NOT EXISTS idx_sim_errors_verified ON sim_errors(verified);",
    "CREATE INDEX IF NOT EXISTS idx_sim_errors_source ON sim_errors(source);",
]

def setup_db():
    print(f"DB 경로: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(CREATE_TABLE_SQL)
    for idx_sql in CREATE_INDEX_SQL:
        cur.execute(idx_sql)

    conn.commit()

    # 확인
    cur.execute("SELECT COUNT(*) FROM sim_errors")
    count = cur.fetchone()[0]
    print(f"✅ sim_errors 테이블 생성 완료 (현재 {count}개 레코드)")

    conn.close()


def setup_chroma():
    """ChromaDB sim_errors_v1 컬렉션 초기화"""
    try:
        import chromadb
        chroma_path = BASE / "db" / "chroma"
        client = chromadb.PersistentClient(path=str(chroma_path))

        # 기존 컬렉션 확인
        existing = [c.name for c in client.list_collections()]
        if "sim_errors_v1" in existing:
            col = client.get_collection("sim_errors_v1")
            print(f"✅ ChromaDB sim_errors_v1 이미 존재 ({col.count()}개 벡터)")
        else:
            col = client.create_collection(
                name="sim_errors_v1",
                metadata={"description": "MEEP 시뮬레이션 오류-해결쌍 벡터 인덱스"}
            )
            print(f"✅ ChromaDB sim_errors_v1 컬렉션 생성 완료")

        print(f"   전체 컬렉션: {[c.name for c in client.list_collections()]}")
    except ImportError:
        print("⚠️  chromadb 없음 — SQLite만 사용")
    except Exception as e:
        print(f"⚠️  ChromaDB 초기화 실패: {e}")


if __name__ == "__main__":
    setup_db()
    setup_chroma()
    print("\n✅ 완료!")
