# Language Support Checklist

이 문서는 현재 GCAI 심볼 추출기가 언어별로 어느 문법을 지원하는지, 아직 지원하지 않는 문법은 무엇인지 정리한 체크리스트입니다.

기준 범위:

- Tree-sitter 기반 파싱
- `Phase 1-2` 심볼 추출
- 검증 기준은 현재 저장소의 pytest 케이스

## Python

### 현재 지원

- [x] 일반 함수 선언
- [x] 비동기 함수 선언
- [x] 클래스 선언
- [x] 클래스 메서드 선언
- [x] 데코레이터가 적용된 함수 선언
- [x] 데코레이터가 적용된 클래스 선언
- [x] 함수 본문 추출
- [x] 메서드 본문 추출
- [x] 모듈 레벨 단순 대입 변수 추출
- [x] 클래스 레벨 단순 대입 변수 추출
- [x] 함수 내부 단순 대입 변수 추출
- [x] 함수/메서드 parameter signature 추출

### 아직 미지원

- [ ] 중첩 클래스/중첩 함수의 계층형 추출
- [ ] tuple/list unpacking 대입 변수 추출
- [ ] `for`, `with`, `except`, comprehension 내부 바인딩 변수 추출
- [ ] `global`, `nonlocal` 선언 추출
- [ ] `lambda` 추출
- [ ] property, descriptor, metaclass 같은 의미론적 분류
- [ ] import / from-import 심볼 추출

## Java

### 현재 지원

- [x] package 이름 반영
- [x] class 선언
- [x] interface 선언
- [x] enum 선언
- [x] enum member 선언
- [x] record 선언
- [x] annotation type 선언
- [x] constructor 선언
- [x] method 선언
- [x] field 변수 추출
- [x] method 내부 local variable 추출
- [x] constructor 내부 local variable 추출
- [x] 메서드/생성자 본문 추출
- [x] 중첩 class 선언의 계층형 추출
- [x] `extends` / `implements` 메타데이터 추출
- [x] import / static import 심볼 추출
- [x] method / constructor parameter 메타데이터 추출

### 아직 미지원

- [ ] 중첩 interface/enum/record 선언의 계층형 추출
- [ ] generic type parameter 메타데이터 추출
- [ ] annotation usage 추출
- [ ] interface default/static method 구분
- [ ] lambda / method reference 추출
- [ ] try-with-resources, enhanced for, catch parameter 바인딩 변수 추출

## C

### 현재 지원

- [x] 전역 함수 선언
- [x] 함수 내부 지역 변수 선언
- [x] 전역 변수 선언
- [x] `typedef struct` 선언
- [x] struct field 추출
- [x] enum 선언
- [x] enum member 추출
- [x] union 선언
- [x] union field 추출
- [x] 함수 본문 추출
- [x] 함수 parameter 메타데이터 추출
- [x] `typedef` alias 추출

### 아직 미지원

- [ ] pointer / array / function pointer 선언의 상세 메타데이터 추출
- [ ] 매크로 기반 선언 해석
- [ ] 전처리기 조건부 분기별 선언 추출
- [ ] anonymous struct/union/enum의 안정적 이름 정책
- [ ] 복수 declarator가 한 declaration에 있는 경우의 정교한 signature 분리
- [ ] parameter 심볼 추출

## C++

### 현재 지원

- [x] namespace 선언
- [x] namespace 내부 함수 선언
- [x] class 선언
- [x] struct 선언
- [x] method 선언
- [x] field 변수 추출
- [x] method 내부 local variable 추출
- [x] enum 선언
- [x] enum member 추출
- [x] union 선언
- [x] union field 추출
- [x] template declaration 내부의 선언 추출
- [x] 함수/메서드 본문 추출
- [x] nested class/struct 선언의 계층형 추출
- [x] inheritance 메타데이터 추출
- [x] typedef / using alias 추출
- [x] using declaration 기반 import 심볼 추출
- [x] 함수/메서드 parameter 메타데이터 추출

### 아직 미지원

- [ ] nested namespace/class/struct의 더 정교한 scope 메타데이터
- [ ] template parameter / specialization 메타데이터 추출
- [ ] constructor / destructor / operator overload 분류
- [ ] lambda / functor / concept / requires clause 추출
- [ ] macro 기반 선언 해석
- [ ] parameter 심볼 추출

## 테스트 범위

현재 pytest로 직접 검증하는 범위:

- [x] Python 파서 동작
- [x] Java 파서 동작
- [x] C 파서 동작
- [x] C++ 파서 동작
- [x] Python 심볼 추출
- [x] Java 심볼 추출
- [x] C 심볼 추출
- [x] C++ 심볼 추출
- [x] `CONTAINS` 관계 추출
- [x] `IMPORTS` 관계 추출
- [x] `CALLS` 관계 추출
- [ ] `READS` / `WRITES` 관계 추출

관련 테스트 파일:

- [tests/test_tree_sitter_parsers.py](/Users/now/Dev/code-ai/gcai/tests/test_tree_sitter_parsers.py:1)
- [tests/test_symbol_extraction_python.py](/Users/now/Dev/code-ai/gcai/tests/test_symbol_extraction_python.py:1)
- [tests/test_symbol_extraction_java.py](/Users/now/Dev/code-ai/gcai/tests/test_symbol_extraction_java.py:1)
- [tests/test_symbol_extraction_c.py](/Users/now/Dev/code-ai/gcai/tests/test_symbol_extraction_c.py:1)
- [tests/test_symbol_extraction_cpp.py](/Users/now/Dev/code-ai/gcai/tests/test_symbol_extraction_cpp.py:1)
- [tests/test_relation_extraction.py](/Users/now/Dev/code-ai/gcai/tests/test_relation_extraction.py:1)
