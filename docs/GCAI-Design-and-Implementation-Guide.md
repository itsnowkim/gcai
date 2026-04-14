# GCAI 설계 및 구현 가이드

## 1. 목표

현재 단계의 목표는 아래 2개 기능을 구현하는 것입니다.

- 입력: `git diff 문서 + local codebase`
- 출력 1: `컨텍스트 패키징`
- 출력 2: `코드 증분 갱신 결과`

여기서 컨텍스트 패키징은 아래를 의미합니다.

- 수정된 코드
- 그래프 탐색으로 얻은 주변 코드

git hook, 리뷰 에이전트, 고급 분석은 이후 확장 대상으로 두고 지금은 제외합니다.

## 2. 기술 스택

- 언어: Python
- 코드 파싱: Tree-sitter
- 그래프 DB: Neo4j
- 벡터 DB: ChromaDB
- API 서버: FastAPI
- 실행 환경: Docker
- 에이전트 제어: LangGraph

현재 구현 범위에서는 LangGraph 사용이 필수는 아니며, 이후 확장 가능하도록 구조만 열어둡니다.

## 3. 핵심 입력 / 출력

### 입력

```json
{
  "repo_path": "/workspace/repo",
  "diff": "diff --git a/src/a.py b/src/a.py ..."
}
```

### 출력 1: 컨텍스트 패키징

```json
{
  "request_id": "req-123",
  "changed_files": ["src/auth/service.py"],
  "changed_symbols": ["AuthService.validate_token"],
  "modified_code": [
    {
      "path": "src/auth/service.py",
      "symbol": "AuthService.validate_token",
      "code": "..."
    }
  ],
  "neighbor_code": [
    {
      "path": "src/session/controller.py",
      "symbol": "SessionController.create_session",
      "code": "..."
    }
  ],
  "graph_paths": [
    "SessionController.create_session -> AuthService.validate_token"
  ]
}
```

### 출력 2: 그래프 증분 갱신

```json
{
  "request_id": "req-124",
  "changed_files": ["src/auth/service.py"],
  "updated_nodes": 12,
  "updated_edges": 18,
  "reindexed_embeddings": 4,
  "status": "success"
}
```

## 4. 저장 구조

### Neo4j

저장 대상:

- File
- Class
- Function
- Variable

최소 관계:

- `CONTAINS`
- `IMPORTS`
- `CALLS`
- `READS`
- `WRITES`

### ChromaDB

저장 대상:

- 함수 구현부 텍스트
- 메서드 구현부 텍스트

용도:

- 변경 코드 주변의 의미적으로 가까운 구현부 검색

## 5. 처리 흐름

### 5.1 초기 색인

1. local codebase 스캔
2. Tree-sitter로 AST 생성
3. 함수, 클래스, 변수 추출
4. 관계 추출
5. Neo4j 적재
6. 함수 구현부를 임베딩하여 ChromaDB 적재

### 5.2 컨텍스트 패키징

1. diff 파싱
2. 변경 파일과 변경 심볼 식별
3. Neo4j에서 변경 심볼 기준 주변 노드 탐색
4. local codebase에서 수정된 코드 추출
5. ChromaDB에서 관련 구현부 보강
6. `modified_code + neighbor_code + graph_paths` 형태로 응답 생성

### 5.3 증분 갱신

1. diff 파싱
2. 변경 파일 식별
3. 변경 파일만 재파싱
4. 기존 그래프 노드/엣지 갱신
5. 변경된 함수 구현부 임베딩 재색인
6. 갱신 결과 요약 반환

## 6. 개발 Phase

### Phase 1. 코드 지식 그래프 추출

구현 항목:

- Tree-sitter 파서 래퍼
- 심볼 추출기
- 관계 추출기
- Neo4j 적재기
- ChromaDB 적재기
- 전체 인덱싱 커맨드

완료 기준:

- local codebase를 읽어 Neo4j와 ChromaDB에 초기 적재 가능

### Phase 2. 컨텍스트 패키징 엔진

구현 항목:

- diff 파서
- 변경 심볼 식별기
- 그래프 탐색기
- 주변 코드 수집기
- 컨텍스트 패키저

완료 기준:

- diff 입력 시 수정된 코드와 주변 코드를 JSON으로 반환 가능

### Phase 3. 증분 갱신 API

구현 항목:

- 그래프 증분 갱신기
- 임베딩 재색인기
- FastAPI 엔드포인트
- Docker 실행 환경

완료 기준:

- 아래 2개 API가 동작
- `POST /analyze/context-package`
- `POST /graph/incremental-update`

## 7. API 정의

### `POST /analyze/context-package`

역할:

- diff를 받아 컨텍스트 패키지 생성

입력:

- `repo_path`
- `diff`

출력:

- `changed_files`
- `changed_symbols`
- `modified_code`
- `neighbor_code`
- `graph_paths`

### `POST /graph/incremental-update`

역할:

- diff를 받아 그래프와 벡터 인덱스를 증분 갱신

입력:

- `repo_path`
- `diff`

출력:

- `changed_files`
- `updated_nodes`
- `updated_edges`
- `reindexed_embeddings`
- `status`

## 8. 권장 디렉토리 구조

```text
gcai/
  app/
    api/
    schemas/
    services/
    storage/
      neo4j/
      chroma/
    parsers/
    analyzers/
  docs/
  Dockerfile
  docker-compose.yml
```

## 9. 제외 범위

현재 문서에서는 아래를 구현 범위에서 제외합니다.

- git hook 연동
- PR bot
- 리뷰 코멘트 생성
- 외부 LLM 호출
- 고급 위험도 점수 모델
- 멀티 리포 분석

## 10. 최종 목표

최종 산출물은 Docker 컨테이너로 실행되는 Python API 서버입니다.

이 서버는 우선 아래 2개 기능만 안정적으로 제공하면 됩니다.

- `diff -> context package`
- `diff -> graph incremental update`
