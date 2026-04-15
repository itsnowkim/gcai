# GCAI User Guide

## 개요

GCAI는 로컬 코드베이스를 분석해 Neo4j와 ChromaDB에 저장하고, 두 가지 API를 제공합니다.

- `POST /analyze/context-package`
  변경 diff 기준으로 수정 코드와 주변 코드를 묶은 컨텍스트 패키지를 반환합니다.
- `POST /graph/incremental-update`
  변경 diff 기준으로 그래프와 벡터 인덱스를 증분 갱신합니다.

권장 사용 순서는 아래와 같습니다.

1. Docker 환경을 띄운다.
2. 초기 색인을 1회 수행한다.
3. 이후 diff를 기준으로 `context-package` 또는 `incremental-update` API를 호출한다.

## API 가이드

### 1. Docker 환경 변수 세팅

프로젝트 루트에서 아래 파일을 준비합니다.

```powershell
Copy-Item .env.example .env
Copy-Item .env.docker.example .env.docker
```

기본적으로 확인할 값은 아래입니다.

- `.env`
  API 내부 설정, Neo4j/Chroma 연결 정보
- `.env.docker`
  호스트 포트와 Docker 볼륨/이미지 설정

기본 포트는 아래와 같습니다.

- API: `8000`
- Neo4j HTTP: `7474`
- Neo4j Bolt: `7687`
- ChromaDB: `8001`

### 2. 컨테이너 실행

Neo4j와 ChromaDB만 먼저 띄우려면:

```powershell
docker compose --env-file .env.docker up -d neo4j chroma
```

API까지 포함해 전체 스택을 띄우려면:

```powershell
docker compose --env-file .env.docker up --build
```

헬스 체크:

```powershell
curl http://localhost:8000/health
```

### 3. 초기 색인

API를 쓰기 전에 대상 코드베이스를 한 번 초기 색인해야 합니다.

로컬에서 직접 실행:

```powershell
py -3.13 -m app.cli.index_codebase . --pretty
```

Docker로 띄운 API 컨테이너는 현재 워크스페이스를 `/workspace`로 읽기 전용 마운트하므로, API 요청에서 `repo_path`는 보통 `/workspace`를 사용하면 됩니다.

### 4. 요청 주소와 포트

기본 API 베이스 주소:

- `http://localhost:8000`

OpenAPI 문서:

- `http://localhost:8000/openapi.json`

엔드포인트:

- `POST http://localhost:8000/analyze/context-package`
- `POST http://localhost:8000/graph/incremental-update`

### 5. 공통 요청 포맷

두 API 모두 같은 요청 형식을 사용합니다.

```json
{
  "repo_path": "/workspace",
  "diff": "diff --git a/app/service.py b/app/service.py\n..."
}
```

필드 설명:

- `repo_path`
  API 프로세스가 접근 가능한 코드베이스 경로
- `diff`
  unified diff 문자열

### 6. Context Package API

요청 예시:

```powershell
curl -X POST http://localhost:8000/analyze/context-package `
  -H "Content-Type: application/json" `
  -d @'
{
  "repo_path": "/workspace",
  "diff": "diff --git a/app/service.py b/app/service.py"
}
'@
```

응답 포맷:

```json
{
  "repo_path": "/workspace",
  "changed_files": [],
  "changed_symbols": [],
  "graph_paths": [],
  "modified_code": [],
  "neighbor_code": []
}
```

주요 응답 필드:

- `changed_files`
  diff에서 식별된 파일과 변경 라인 정보
- `changed_symbols`
  변경 라인에 걸린 심볼 seed 목록
- `graph_paths`
  Neo4j 기반 주변 그래프 경로
- `modified_code`
  변경된 코드 스니펫
- `neighbor_code`
  그래프/벡터 기반 주변 코드 스니펫

### 7. Incremental Update API

요청 예시:

```powershell
curl -X POST http://localhost:8000/graph/incremental-update `
  -H "Content-Type: application/json" `
  -d @'
{
  "repo_path": "/workspace",
  "diff": "diff --git a/app/service.py b/app/service.py"
}
'@
```

응답 포맷:

```json
{
  "changed_files": [
    "app/service.py"
  ],
  "updated_nodes": 5,
  "updated_edges": 8,
  "reindexed_embeddings": 2,
  "status": "ok"
}
```

주요 응답 필드:

- `changed_files`
  diff에서 식별된 대상 파일 목록
- `updated_nodes`
  이번 요청에서 갱신된 Neo4j symbol 수
- `updated_edges`
  이번 요청에서 갱신된 Neo4j relation 수
- `reindexed_embeddings`
  이번 요청에서 다시 색인된 Chroma callable document 수
- `status`
  현재는 성공 시 `ok`

### 8. 오류 응답 포맷

비정상 요청이나 서비스 오류 시 아래 형식으로 응답합니다.

```json
{
  "request_id": "req-123",
  "error_code": "diff_parse_error",
  "message": "Unexpected diff content before file header at line 1: not a diff"
}
```

자주 볼 수 있는 오류:

- `invalid_repo_path`
- `diff_parse_error`
- `source_parse_error`
- `neo4j_*`
- `chroma_*`

## 테스트 가이드

### 1. 전체 회귀 테스트

가장 먼저 확인할 기본 명령입니다.

```powershell
py -3.13 -m pytest -q tests
```

### 2. 모듈별 테스트

파서 / 심볼 / 관계:

```powershell
py -3.13 -m pytest -q tests/test_tree_sitter_parsers.py
py -3.13 -m pytest -q tests/test_symbol_extraction_python.py tests/test_symbol_extraction_java.py tests/test_symbol_extraction_c.py tests/test_symbol_extraction_cpp.py
py -3.13 -m pytest -q tests/test_relation_extraction.py
```

코드베이스 스캔 / 초기 색인:

```powershell
py -3.13 -m pytest -q tests/test_codebase_scan.py tests/test_indexing.py tests/test_index_verification.py
```

Neo4j / Chroma 저장소:

```powershell
py -3.13 -m pytest -q tests/test_neo4j_storage.py
py -3.13 -m pytest -q tests/test_chroma_storage.py
```

컨텍스트 패키지:

```powershell
py -3.13 -m pytest -q tests/test_changed_code_context.py tests/test_context_package.py tests/test_graph_explore.py
py -3.13 -m pytest -q tests/test_context_package_api.py
```

증분 갱신:

```powershell
py -3.13 -m pytest -q tests/test_incremental_update_step1.py
py -3.13 -m pytest -q tests/test_incremental_update_service.py
py -3.13 -m pytest -q tests/test_incremental_update_api.py
```

애플리케이션/라우팅:

```powershell
py -3.13 -m pytest -q tests/test_api_app.py
```

### 3. 통합 테스트

통합 테스트는 Neo4j와 ChromaDB가 실행 중이어야 합니다.

먼저 스토리지를 기동합니다.

```powershell
docker compose --env-file .env.docker up -d neo4j chroma
```

그래프 탐색 통합 테스트:

```powershell
py -3.13 -m pytest -q tests/test_graph_explore_integration.py
```

증분 갱신 통합 테스트:

```powershell
py -3.13 -m pytest -q tests/test_incremental_update_integration.py
```

주의:

- 실DB를 직접 비우고 다시 적재하는 테스트가 포함되어 있으므로 통합 테스트는 병렬 실행보다 순차 실행을 권장합니다.
- 로컬 환경에서 `.pytest_cache` 관련 권한 경고가 보일 수 있지만, 테스트 통과/실패와 직접 관련이 없는 경우가 많습니다.

## 운영 팁

### 1. `repo_path`는 API 프로세스 기준 경로여야 합니다

로컬 Python 프로세스로 실행하면 예를 들어 `C:/project/my-repo` 같은 경로를 줄 수 있습니다.  
Docker로 실행한 API에 요청하면 현재 compose 설정상 워크스페이스가 `/workspace`로 마운트되므로 `repo_path`는 `/workspace`를 쓰는 것이 일반적입니다.

### 2. 증분 갱신 전에 초기 색인이 필요합니다

`/graph/incremental-update`는 기존 인덱스를 기준으로 동작합니다.  
초기 색인을 하지 않은 상태에서는 기대한 결과를 얻기 어렵습니다.

### 3. diff 포맷은 unified diff여야 합니다

예를 들어 `git diff` 출력 그대로 보내는 방식이 가장 안전합니다.

### 4. 확인이 필요하면 OpenAPI를 먼저 봅니다

필드가 헷갈리면 아래 주소에서 현재 서버 기준 계약을 확인할 수 있습니다.

- `http://localhost:8000/openapi.json`
