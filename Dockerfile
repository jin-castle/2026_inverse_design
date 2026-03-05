FROM python:3.11-slim

# 시스템 패키지
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# sentence-transformers 모델 사전 다운로드 (빌드 시 캐시)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

# 소스 코드 복사
COPY agent/    ./agent/
COPY api/      ./api/
COPY query/    ./query/
COPY web/      ./web/
COPY search_agent.py .

# DB 파일 복사
COPY db/knowledge.db           ./db/knowledge.db
COPY db/knowledge_graph_v2.pkl ./db/knowledge_graph_v2.pkl
COPY db/chroma/                ./db/chroma/

# 환경 변수
ENV APP_DIR=/app
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

# HuggingFace Spaces 기본 포트
EXPOSE 7860

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
