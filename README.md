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
- Tree-sitter 언어 로딩은 공식 언어별 패키지(`tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript`)를 사용합니다.
- 요청 ID는 `X-Request-ID` 헤더를 우선 재사용하고, 없으면 `req-<hex>` 형식으로 생성합니다.

## Phase 1-1 범위

- 초기 지원 언어 범위는 `Python`, `Java`, `C`, `C++`입니다.
- 파일 확장자 기준으로 Tree-sitter 언어를 선택합니다.
- 단일 파일 파싱은 문법 오류를 기본적으로 실패로 처리합니다.

## Phase 1-2 범위

- 심볼 추출은 공통 스키마와 언어별 모듈로 분리되어 있습니다.
- 언어별 extractor는 `app/analyzers/symbols/python.py`, `java.py`, `c.py`, `cpp.py`에 위치합니다.
- 추출 대상 심볼은 `file`, `import`, `namespace`, `class`, `struct`, `interface`, `enum`, `enum_member`, `union`, `record`, `annotation`, `function`, `method`, `constructor`, `variable`, `type_alias`입니다.
- 공통 메타데이터는 `qualified_name`, `signature`, `parameters`, `super_types`, `aliased_type`, `start_line`, `end_line`를 포함합니다.
- Java는 `package`, `import/static import`, nested class, `extends/implements`, constructor parameter를 포함합니다.
- C/C++는 `typedef`/`using` alias, function parameter와 C++ `namespace`, nested class/struct, inheritance, `using` declaration을 포함합니다.
- Python은 데코레이터가 있는 클래스/함수와 비동기 함수까지 포함합니다.

## Phase 1-4 범위

- `app/services/codebase_scan.py`의 `scan_codebase(...)`가 `repo_path` 전체를 순회합니다.
- 지원 확장자만 분석 대상으로 삼고, 미지원 파일은 `unsupported_language`로 스킵합니다.
- 기본 제외 디렉토리는 `.git`, `.venv`, `node_modules`, `dist`, `build`, `__pycache__` 등을 포함합니다.
- 기본 대용량 파일 제외 기준은 `512 KiB`입니다.
- 스캔 결과는 파일별 `symbols`, `relations`, 스킵 사유를 함께 반환합니다.

## Phase 1-5 범위

- `app/storage/neo4j/client.py`가 driver 생성과 연결 확인을 담당합니다.
- `app/storage/neo4j/schema.py`가 제약 조건 생성 책임을 가집니다.
- `app/storage/neo4j/writer.py`는 `UNWIND` 기반 배치 upsert를 수행합니다.
- 노드와 엣지는 `MERGE` 기반으로 upsert되며, 재적재 시 `id`를 기준으로 갱신됩니다.
- `app/services/graph_ingest.py`의 `ingest_scan_result_to_neo4j(...)`가 스캔 결과 전체를 적재하고 통계를 반환합니다.
