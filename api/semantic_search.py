"""
semantic_search.py
==================
fastembed + BAAI/bge-small-en-v1.5 기반 시맨틱 검색 엔진.

아키텍처:
  1. 서버 시작 시 sim_errors (high+medium) 전체 임베딩 → numpy array 캐시
  2. 쿼리: 에러메시지 + 코드 스니펫 → embedding → cosine similarity
  3. OOD threshold (0.40): 미지 에러 감지
  4. 새 레코드 ingest 시 실시간 인덱스 갱신
"""
from __future__ import annotations
import numpy as np
import sqlite3
import logging
import time
import os
from typing import Optional

logger = logging.getLogger("semantic_search")

# ── 상수 ─────────────────────────────────────────────────────────────────────
MODEL_NAME   = "BAAI/bge-small-en-v1.5"
OOD_LOW      = 0.40   # 이 미만: 미지 에러 (관련 없음)
OOD_MED      = 0.60   # 이 미만: 낮은 신뢰도
DB_PATH      = "/app/db/knowledge.db"
EMBED_TABLE  = "sim_errors_embeddings"

# ── 싱글톤 상태 ───────────────────────────────────────────────────────────────
_model       = None
_kb_ids      = []          # sim_errors.id 목록 (인덱스 순서)
_kb_texts    = []          # 임베딩에 사용한 텍스트
_kb_embeddings = None      # shape (N, 384)


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        logger.info(f"Loading fastembed model: {MODEL_NAME}")
        t0 = time.time()
        _model = TextEmbedding(MODEL_NAME)
        logger.info(f"Model loaded in {time.time()-t0:.2f}s")
    return _model


def _build_text(row: dict) -> str:
    """임베딩 입력 텍스트 구성: error_message + error_type + 핵심 필드."""
    parts = []
    if row.get("error_type"):
        parts.append(f"[{row['error_type']}]")
    if row.get("error_message"):
        parts.append(row["error_message"][:300])
    if row.get("root_cause"):
        parts.append(row["root_cause"][:200])
    if row.get("fix_description"):
        parts.append(row["fix_description"][:150])
    if row.get("fix_keywords"):
        parts.append(row["fix_keywords"][:100])
    return " ".join(parts)[:700]


def build_index(db_path: str = DB_PATH) -> int:
    """
    DB에서 high+medium 레코드를 가져와 임베딩 인덱스 구축.
    서버 시작 시 1회 실행 (3-4초).
    반환: 인덱스에 포함된 레코드 수
    """
    global _kb_ids, _kb_texts, _kb_embeddings

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, error_type, error_message, root_cause,
               fix_description, fix_keywords, fixed_code, confidence
        FROM sim_errors
        WHERE confidence IN ('high', 'medium')
          AND (error_message IS NOT NULL AND error_message != '')
        ORDER BY id
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("No records found for embedding index")
        return 0

    model = _get_model()
    texts = [_build_text(dict(r)) for r in rows]
    ids   = [r["id"] for r in rows]

    logger.info(f"Encoding {len(texts)} records...")
    t0 = time.time()
    embeddings = np.array(list(model.embed(texts, batch_size=64)))
    logger.info(f"Encoded in {time.time()-t0:.2f}s, shape={embeddings.shape}")

    _kb_ids        = ids
    _kb_texts      = texts
    _kb_embeddings = embeddings

    return len(ids)


def add_to_index(record_id: int, db_path: str = DB_PATH) -> bool:
    """
    새 레코드 ingest 후 실시간으로 인덱스에 추가.
    기존 인덱스를 rebuild하지 않고 append.
    """
    global _kb_ids, _kb_texts, _kb_embeddings

    if _kb_embeddings is None:
        return False  # 인덱스 미구축

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, error_type, error_message, root_cause,
               fix_description, fix_keywords, confidence
        FROM sim_errors
        WHERE id = ? AND confidence IN ('high', 'medium')
    """, (record_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False  # low confidence → 인덱스 제외

    text  = _build_text(dict(row))
    model = _get_model()
    emb   = np.array(list(model.embed([text])))  # shape (1, 384)

    # 중복 방지
    if record_id in _kb_ids:
        idx = _kb_ids.index(record_id)
        _kb_embeddings[idx] = emb[0]
        _kb_texts[idx]      = text
        logger.debug(f"Updated embedding for id={record_id}")
    else:
        _kb_ids.append(record_id)
        _kb_texts.append(text)
        _kb_embeddings = np.vstack([_kb_embeddings, emb])
        logger.debug(f"Added embedding for id={record_id}, index size={len(_kb_ids)}")

    return True


def search(
    query: str,
    n: int = 5,
    db_path: str = DB_PATH,
    ood_threshold: float = OOD_LOW,
) -> list[dict]:
    """
    시맨틱 검색 실행.
    반환: [{"id", "score", "confidence_level", "is_ood", ...}]
    is_ood=True이면 score<threshold → 미지 에러로 판정.
    """
    if _kb_embeddings is None or len(_kb_ids) == 0:
        logger.warning("Embedding index not built")
        return []

    model = _get_model()
    from sklearn.metrics.pairwise import cosine_similarity

    t0    = time.time()
    q_emb = np.array(list(model.embed([query[:700]])))  # (1, 384)
    sims  = cosine_similarity(q_emb, _kb_embeddings)[0]
    elapsed = (time.time() - t0) * 1000

    # 상위 n개
    top_n  = min(n, len(_kb_ids))
    top_idx = np.argsort(sims)[::-1][:top_n]
    top_ids   = [_kb_ids[i]   for i in top_idx]
    top_scores = [float(sims[i]) for i in top_idx]

    best_score = top_scores[0] if top_scores else 0.0
    is_ood     = best_score < ood_threshold

    # DB에서 상세 데이터 조회
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    placeholders = ",".join("?" * len(top_ids))
    cur.execute(f"""
        SELECT id, error_type, error_message, root_cause,
               fix_description, fixed_code, original_code,
               fix_keywords, pattern_name, source, confidence, fix_worked
        FROM sim_errors WHERE id IN ({placeholders})
    """, top_ids)
    rows_by_id = {r["id"]: dict(r) for r in cur.fetchall()}
    conn.close()

    results = []
    for rid, score in zip(top_ids, top_scores):
        if rid not in rows_by_id:
            continue
        row = rows_by_id[rid]

        # 신뢰도 수준 분류
        if score >= 0.60:
            conf_level = "high_match"
        elif score >= ood_threshold:
            conf_level = "medium_match"
        else:
            conf_level = "no_match"

        results.append({
            "id":           rid,
            "score":        score,
            "confidence_level": conf_level,
            "is_ood":       score < ood_threshold,
            "elapsed_ms":   round(elapsed, 2),
            **{k: row.get(k, "") for k in [
                "error_type", "error_message", "root_cause",
                "fix_description", "fixed_code", "original_code",
                "source", "confidence", "fix_worked",
            ]},
        })

    logger.debug(
        f"search: query={query[:50]!r} best_score={best_score:.3f} "
        f"is_ood={is_ood} elapsed={elapsed:.1f}ms"
    )
    return results


def index_size() -> int:
    return len(_kb_ids)
