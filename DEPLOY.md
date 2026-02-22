# MEEP-KB 배포 가이드

## 옵션 1: 로컬 Docker (빠른 내부 공유)

```bash
# 1. .env 파일 생성
cp .env.example .env
# .env에 실제 API 키 입력

# 2. 빌드 (처음 한 번, ~15분 — 모델 다운로드 포함)
docker-compose build

# 3. 실행
docker-compose up -d

# 4. 접속
# http://localhost:8765/
```

---

## 옵션 2: Railway.app (외부 공유, 추천)

### 준비
1. https://railway.app 회원가입 (GitHub 로그인)
2. GitHub에 meep-kb 레포 push

### 주의: DB 파일 크기 문제
- `db/chroma/` 폴더가 수백 MB일 수 있음 → GitHub에 올리기 어려움
- **해결책**: ChromaDB를 Railway Volume에 마운트하거나, 배포 시 DB 재생성

### Railway 배포 단계
```bash
# 1. .gitignore 설정 (큰 파일 제외)
echo "db/chroma/" >> .gitignore
echo "*.pkl" >> .gitignore      # 그래프는 배포 시 재생성

# 2. GitHub push
git init
git add .
git commit -m "MEEP-KB initial"
git remote add origin https://github.com/<yourname>/meep-kb
git push -u origin main

# 3. Railway에서
# - New Project → GitHub 연결 → meep-kb 선택
# - Variables: ANTHROPIC_API_KEY=sk-ant-...
# - Deploy 클릭
```

---

## 옵션 3: eidl 서버 직접 배포 (VPS, 최적)

Jin의 기존 서버(eidl-a6000, 4090)에 직접 배포:

```bash
# 서버에서
git clone https://github.com/<yourname>/meep-kb /opt/meep-kb
cd /opt/meep-kb

# DB 파일은 scp로 별도 전송
scp -r db/ user@eidl-server:/opt/meep-kb/

# Docker 실행
docker-compose up -d

# Nginx 리버스 프록시 (선택)
# → 도메인 연결 가능
```

---

## DB 파일 크기 확인

```bash
wsl -u root -e bash -c "du -sh /mnt/c/Users/user/projects/meep-kb/db/*"
```

## 현재 서버 상태 확인

```bash
curl http://localhost:8765/api/status
```
