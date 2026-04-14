# GCAI Roadmap

이 문서는 실제 개발 진행 순서에 맞춘 작업 체크리스트입니다.

## Phase 0. 프로젝트 초기 세팅

- [ ] Python 프로젝트 기본 디렉토리 구조 생성
- [ ] `app/api`, `app/schemas`, `app/services`, `app/storage`, `app/parsers`, `app/analyzers` 디렉토리 생성
- [ ] Python 패키지 초기화 파일(`__init__.py`) 추가
- [ ] 의존성 관리 파일 작성
- [ ] FastAPI, Neo4j client, ChromaDB client, Tree-sitter 관련 라이브러리 선정
- [ ] 개발용 실행 방법 정의
- [ ] 환경 변수 목록 정리
- [ ] `.env.example` 작성
- [ ] 기본 설정 로더 작성
- [ ] 로깅 설정 작성
- [ ] 예외 처리 기본 구조 작성
- [ ] request id 생성 방식 정의

## Phase 1. 코드 지식 그래프 추출

### 1-1. Tree-sitter 파서 기반 준비

- [ ] 지원할 첫 번째 언어 범위 확정
- [ ] Tree-sitter 언어 로더 구현
- [ ] 파일 확장자와 Tree-sitter 언어 매핑 정의
- [ ] 파일 읽기 유틸 작성
- [ ] 단일 파일 AST 생성 함수 구현
- [ ] 파싱 실패 시 예외 처리 정의
- [ ] 파싱 결과 디버깅용 출력 함수 작성

### 1-2. 심볼 추출

- [ ] File 노드 추출 로직 구현
- [ ] Class 노드 추출 로직 구현
- [ ] Function 노드 추출 로직 구현
- [ ] Variable 노드 추출 로직 구현
- [ ] 각 노드의 공통 메타데이터 정의
- [ ] `id` 생성 규칙 정의
- [ ] `path`, `name`, `signature`, `start_line`, `end_line` 추출 규칙 구현
- [ ] 함수 본문 추출 로직 구현
- [ ] 클래스 메서드 추출 로직 구현
- [ ] 추출 결과를 공통 schema로 변환

### 1-3. 관계 추출

- [ ] `CONTAINS` 관계 추출 구현
- [ ] `IMPORTS` 관계 추출 구현
- [ ] `CALLS` 관계 추출 구현
- [ ] `READS` 관계 추출 구현
- [ ] `WRITES` 관계 추출 구현
- [ ] 관계별 source/destination 규칙 정의
- [ ] 관계 중복 제거 로직 구현
- [ ] 관계 추출 결과 schema 정의

### 1-4. 로컬 코드베이스 스캔

- [ ] `repo_path` 기준 파일 순회 로직 구현
- [ ] 분석 대상 파일 필터 정의
- [ ] 제외 디렉토리 규칙 정의
- [ ] 대용량 파일 제외 규칙 정의
- [ ] 언어 미지원 파일 스킵 처리 구현
- [ ] 전체 코드베이스 스캔 서비스 구현

### 1-5. Neo4j 적재

- [ ] Neo4j 연결 설정 구현
- [ ] 연결 확인 함수 구현
- [ ] 노드 upsert 쿼리 작성
- [ ] 엣지 upsert 쿼리 작성
- [ ] 배치 적재 로직 작성
- [ ] 동일 심볼 재적재 시 갱신 정책 정의
- [ ] 전체 적재 서비스 구현
- [ ] 적재 결과 통계 반환 구현

### 1-6. ChromaDB 적재

- [ ] ChromaDB 연결 설정 구현
- [ ] 컬렉션 이름 규칙 정의
- [ ] 함수 구현부 document 포맷 정의
- [ ] document metadata 포맷 정의
- [ ] 임베딩 생성 방식 정의
- [ ] 함수 구현부 저장 로직 작성
- [ ] 메서드 구현부 저장 로직 작성
- [ ] 재색인 시 upsert 정책 구현
- [ ] 적재 결과 통계 반환 구현

### 1-7. 초기 색인 실행기

- [ ] 전체 색인 서비스 조합
- [ ] `repo_path` 입력 검증 구현
- [ ] 초기 색인 CLI 또는 실행 함수 작성
- [ ] 초기 색인 성공/실패 로그 정리
- [ ] 샘플 저장소 기준 1회 실행 검증
- [ ] Neo4j 적재 결과 확인
- [ ] ChromaDB 적재 결과 확인

### Phase 1 완료 기준

- [ ] local codebase를 읽어 Neo4j와 ChromaDB에 초기 적재 가능

## Phase 2. 컨텍스트 패키징 엔진

### 2-1. Diff 파서

- [ ] unified diff 포맷 파서 구현
- [ ] 변경 파일 목록 추출 구현
- [ ] 추가/수정/삭제 파일 구분 로직 구현
- [ ] 변경 라인 범위 추출 구현
- [ ] diff에서 대상 파일 path 정규화 구현
- [ ] diff 파싱 실패 처리 구현

### 2-2. 변경 심볼 식별

- [ ] 변경 파일 기준 source code 로드 구현
- [ ] 변경 라인과 AST 노드 매핑 구현
- [ ] 변경 라인이 속한 함수 식별 구현
- [ ] 변경 라인이 속한 클래스 식별 구현
- [ ] 변경 심볼 목록 생성 로직 구현
- [ ] 변경 심볼 중복 제거 처리 구현

### 2-3. 그래프 탐색

- [ ] 변경 심볼을 seed node로 변환
- [ ] Neo4j 조회 서비스 구현
- [ ] 1-hop 주변 노드 탐색 구현
- [ ] 2-hop 확장 탐색 구현
- [ ] 탐색 대상 관계 allowlist 정의
- [ ] 탐색 깊이 제한 설정 구현
- [ ] graph path 복원 로직 구현
- [ ] 그래프 탐색 결과 정렬 기준 정의

### 2-4. 수정 코드 추출

- [ ] 변경 파일 원문 로드 구현
- [ ] 변경 심볼 기준 코드 블록 추출 구현
- [ ] 함수 단위 코드 스니펫 생성
- [ ] 클래스 단위 코드 스니펫 생성
- [ ] `modified_code` 응답 schema 정의

### 2-5. 주변 코드 수집

- [ ] 그래프 탐색 결과에서 관련 심볼 목록 수집
- [ ] local codebase에서 주변 심볼 코드 추출
- [ ] ChromaDB 유사 코드 검색 구현
- [ ] 그래프 기반 결과와 벡터 기반 결과 병합
- [ ] 중복 코드 제거 로직 구현
- [ ] `neighbor_code` 응답 schema 정의

### 2-6. 컨텍스트 패키지 생성

- [ ] `changed_files` 생성 로직 구현
- [ ] `changed_symbols` 생성 로직 구현
- [ ] `graph_paths` 생성 로직 구현
- [ ] `modified_code` 구성 로직 구현
- [ ] `neighbor_code` 구성 로직 구현
- [ ] 최종 context package schema 작성
- [ ] JSON 응답 직렬화 검증

### 2-7. 서비스 검증

- [ ] 샘플 diff 준비
- [ ] 단일 함수 수정 케이스 검증
- [ ] 클래스 메서드 수정 케이스 검증
- [ ] import 변경 케이스 검증
- [ ] 변경 심볼을 찾지 못한 경우 처리 검증
- [ ] 빈 주변 코드 결과 처리 검증

### Phase 2 완료 기준

- [ ] diff 입력 시 수정된 코드와 주변 코드를 JSON으로 반환 가능

## Phase 3. 그래프 증분 갱신

### 3-1. 변경 파일 기반 재분석

- [ ] diff에서 변경 파일 목록 재사용
- [ ] 삭제 파일 처리 정책 정의
- [ ] 변경 파일 재파싱 구현
- [ ] 변경 파일의 최신 심볼 목록 재추출
- [ ] 변경 파일의 최신 관계 목록 재추출

### 3-2. Neo4j 증분 갱신

- [ ] 기존 파일 관련 노드 조회 구현
- [ ] 기존 파일 관련 엣지 조회 구현
- [ ] 삭제 대상 노드 판별 로직 구현
- [ ] 삭제 대상 엣지 판별 로직 구현
- [ ] 갱신 대상 노드 upsert 구현
- [ ] 갱신 대상 엣지 upsert 구현
- [ ] 파일 삭제 시 그래프 정리 로직 구현
- [ ] `updated_nodes`, `updated_edges` 집계 구현

### 3-3. ChromaDB 재색인

- [ ] 변경 파일 기준 기존 document 조회 구현
- [ ] 삭제 대상 document 제거 구현
- [ ] 최신 함수 구현부 재임베딩 구현
- [ ] 최신 메서드 구현부 재임베딩 구현
- [ ] upsert 결과 집계 구현
- [ ] `reindexed_embeddings` 계산 구현

### 3-4. 갱신 결과 응답

- [ ] 증분 갱신 결과 schema 작성
- [ ] `changed_files` 구성 로직 구현
- [ ] `status` 규칙 정의
- [ ] 실패 시 오류 응답 포맷 정의

### 3-5. 서비스 검증

- [ ] 함수 본문 수정 케이스 검증
- [ ] 함수 추가 케이스 검증
- [ ] 함수 삭제 케이스 검증
- [ ] import 변경 케이스 검증
- [ ] 파일 삭제 케이스 검증
- [ ] Neo4j 갱신 결과 검증
- [ ] ChromaDB 재색인 결과 검증

### Phase 3 완료 기준

- [ ] diff 기반 그래프/벡터 증분 갱신 가능

## Phase 4. API 서버

### 4-1. FastAPI 기본 구성

- [ ] FastAPI 앱 생성
- [ ] 헬스 체크 엔드포인트 구현
- [ ] 공통 예외 처리기 등록
- [ ] request/response schema 연결
- [ ] 설정 로더와 앱 초기화 연결

### 4-2. Context Package API

- [ ] `POST /analyze/context-package` 엔드포인트 구현
- [ ] 요청 body 검증 구현
- [ ] 서비스 계층 연결
- [ ] 응답 schema 반환 구현
- [ ] 실패 응답 처리 구현

### 4-3. Incremental Update API

- [ ] `POST /graph/incremental-update` 엔드포인트 구현
- [ ] 요청 body 검증 구현
- [ ] 서비스 계층 연결
- [ ] 응답 schema 반환 구현
- [ ] 실패 응답 처리 구현

### 4-4. API 검증

- [ ] OpenAPI 문서 확인
- [ ] 샘플 요청으로 context-package API 검증
- [ ] 샘플 요청으로 incremental-update API 검증
- [ ] 잘못된 `repo_path` 입력 검증
- [ ] 잘못된 diff 입력 검증

### Phase 4 완료 기준

- [ ] 아래 2개 API가 동작
- [ ] `POST /analyze/context-package`
- [ ] `POST /graph/incremental-update`

## Phase 5. Docker 실행 환경

### 5-1. 애플리케이션 컨테이너

- [ ] `Dockerfile` 작성
- [ ] Python 런타임 이미지 선정
- [ ] 애플리케이션 실행 커맨드 정의
- [ ] 환경 변수 주입 방식 정의

### 5-2. 로컬 통합 실행

- [ ] `docker-compose.yml` 작성
- [ ] FastAPI 서비스 정의
- [ ] Neo4j 서비스 정의
- [ ] ChromaDB 서비스 정의
- [ ] 서비스 간 연결 설정
- [ ] 볼륨 마운트 설정

### 5-3. 실행 검증

- [ ] docker compose로 전체 기동 확인
- [ ] API 서버 접속 확인
- [ ] Neo4j 연결 확인
- [ ] ChromaDB 연결 확인
- [ ] context-package API end-to-end 검증
- [ ] incremental-update API end-to-end 검증

### Phase 5 완료 기준

- [ ] Docker 환경에서 전체 시스템 실행 가능

## 최종 완료 기준

- [ ] local codebase 초기 색인 가능
- [ ] diff 기준 컨텍스트 패키징 가능
- [ ] diff 기준 그래프 증분 갱신 가능
- [ ] FastAPI 엔드포인트 2개 동작
- [ ] Docker 환경에서 end-to-end 실행 가능
