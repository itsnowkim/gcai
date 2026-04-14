# GCAI

Graph based Code AI(GCAI)는 대규모 코드베이스를 그래프로 모델링하고, 코드 변경(Diff) 발생 시 영향도와 잠재적 오류를 분석하는 AI 에이전트 시스템을 목표로 합니다.

주요 문서:

- [GCAI 설계 및 구현 가이드](docs/GCAI-Design-and-Implementation-Guide.md)
- [GCAI 로드맵](docs/Roadmap.md)

## 현재 구현 범위

현재 저장소에서 검증 가능한 주요 범위는 `Phase 1`입니다.

- Tree-sitter 기반 파싱
- 심볼/관계 추출
- 로컬 코드베이스 스캔
- Neo4j 적재
- ChromaDB 적재
- 초기 색인 CLI 실행
- `/health` 엔드포인트

## 셋업 요구사항

- Python `3.11+`
- `pip`
- Docker Desktop
- Docker Compose

권장 로컬 확인 명령:

```bash
python --version
docker --version
docker compose version
```

Windows에서는 `py -3.13` 같은 Python launcher 사용을 권장합니다.

## 빠른 시작

### 1. 의존성 설치

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
py -3.13 -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

### 2. 환경 변수 확인

기본 `.env.example`은 로컬에서 직접 DB를 띄우거나 `docker compose`로 Neo4j/Chroma를 붙일 수 있는 값으로 맞춰져 있습니다.

중요 기본값:

- `NEO4J_URI=bolt://localhost:7687`
- `NEO4J_USERNAME=neo4j`
- `NEO4J_PASSWORD=neo4jpass123`
- `CHROMA_HOST=localhost`
- `CHROMA_PORT=8001`
- `TREE_SITTER_LANGUAGES=python,java,c,cpp`

## 로컬 실행

API 서버 실행:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

헬스 체크:

```bash
curl http://localhost:8000/health
```

## Docker 실행

전체 스택 실행:

```bash
docker compose up --build
```

스토리지만 먼저 실행:

```bash
docker compose up -d neo4j chroma
```

기본 포트:

- GCAI API: `8000`
- Neo4j HTTP: `7474`
- Neo4j Bolt: `7687`
- ChromaDB: `8001`

## 초기 색인 실행

로컬 저장소를 Neo4j와 ChromaDB에 초기 적재합니다.

```bash
python -m app.cli.index_codebase . --pretty
```

예상 결과:

```json
{
  "repo_path": "...",
  "scanned_files": 0,
  "skipped_files": 0,
  "upserted_nodes": 0,
  "upserted_edges": 0,
  "upserted_documents": 0
}
```

참고:

- Chroma 임베딩 모델은 첫 실행 시 다운로드될 수 있습니다.
- 네트워크가 제한된 환경에서는 첫 Chroma 적재가 실패할 수 있습니다.

## 테스트와 검증

전체 테스트 실행:

```bash
pytest -q tests
```

Windows PowerShell 예시:

```powershell
py -3.13 -m pytest -q tests
```

권장 검증 순서:

1. `pytest -q tests`
2. `docker compose up -d neo4j chroma`
3. `python -m app.cli.index_codebase . --pretty`
4. 필요 시 `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## 환경 변수

| 이름 | 설명 | 기본값 |
| --- | --- | --- |
| `APP_NAME` | 서비스 이름 | `GCAI` |
| `APP_ENV` | 실행 환경 | `local` |
| `APP_HOST` | 바인딩 호스트 | `0.0.0.0` |
| `APP_PORT` | 바인딩 포트 | `8000` |
| `APP_LOG_LEVEL` | 로깅 레벨 | `INFO` |
| `APP_DEBUG` | FastAPI debug 모드 | `false` |
| `NEO4J_URI` | Neo4j 연결 URI | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Neo4j 사용자 이름 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 비밀번호 | `neo4jpass123` |
| `NEO4J_DATABASE` | Neo4j 데이터베이스 | `neo4j` |
| `CHROMA_HOST` | ChromaDB 호스트 | `localhost` |
| `CHROMA_PORT` | ChromaDB 포트 | `8001` |
| `CHROMA_COLLECTION_PREFIX` | Chroma 컬렉션 접두어 | `gcai` |
| `TREE_SITTER_LANGUAGES` | 초기 지원 언어 목록 | `python,java,c,cpp` |
