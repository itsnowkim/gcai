# GCAI

Graph based Code AI(GCAI)는 대규모 코드베이스를 그래프로 모델링하고, 코드 변경(Diff) 발생 시 영향도와 잠재적 오류를 분석하는 AI 에이전트 시스템을 목표로 합니다.

주요 기술 문서:

- [GCAI 설계 및 구현 가이드](/Users/now/Dev/code-ai/gcai/docs/GCAI-Design-and-Implementation-Guide.md)
- [GCAI 로드맵](/Users/now/Dev/code-ai/gcai/docs/Roadmap.md)

## 개발 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

헬스 체크:

```bash
curl http://localhost:8000/health
```

Docker 실행:

```bash
docker-compose up --build
```

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
| `NEO4J_PASSWORD` | Neo4j 비밀번호 | `neo4j` |
| `NEO4J_DATABASE` | Neo4j 데이터베이스 | `neo4j` |
| `CHROMA_HOST` | ChromaDB 호스트 | `localhost` |
| `CHROMA_PORT` | ChromaDB 포트 | `8001` |
| `CHROMA_COLLECTION_PREFIX` | Chroma 컬렉션 접두어 | `gcai` |
| `TREE_SITTER_LANGUAGES` | 초기 지원 언어 목록 | `python,javascript,typescript` |

## Phase 0 결정사항

- API 서버 프레임워크는 `FastAPI`를 사용합니다.
- 그래프 저장소 클라이언트는 `neo4j` Python driver를 사용합니다.
- 벡터 저장소 클라이언트는 `chromadb`를 사용합니다.
- Tree-sitter 언어 로딩은 `tree-sitter-language-pack`을 우선 사용합니다.
- 요청 ID는 `X-Request-ID` 헤더를 우선 재사용하고, 없으면 `req-<hex>` 형식으로 생성합니다.
