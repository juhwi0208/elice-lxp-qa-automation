# API Automation

`api/`는 엘리스 LXP의 핵심 기능을 대상으로 **정상 기능, 입력값 검증,
인증·권한 경계, 응답 계약, 상태 변경 후 원복**을 검증하는 pytest 기반
API 자동화 모듈입니다.

단순 요청 성공 여부만 확인하지 않고, 자동화 실행 자체가 QA 환경과
데이터에 영향을 주지 않도록 요청 제한, Host 검증, 5xx 중단, 상태 변경
보호, Cleanup 구조를 함께 구현했습니다.

## 1. 기술 구성

-   Python 3.11
-   pytest
-   requests
-   python-dotenv
-   Allure pytest
-   pytest-rerunfailures
-   Google Sheets API 연동 스크립트

API 전용 의존성은 `api/requirements.txt`에 정의되어 있습니다.

## 2. 디렉터리 구조

``` text
api/
├── tests/
│   ├── common_auth/       # 공통 인증·안전장치·응답 판정 자체 검증
│   ├── classroom_home/    # 클래스 홈 API
│   ├── course_list/       # 학습 과목·수업·자료·변경 경계
│   ├── class_schedule/    # 수업 일정 및 입력/권한 경계
│   └── board/             # 게시판 조회·생성·수정·권한·검증
├── utils/
│   ├── api_client.py      # 요청 실행, Host/변이/5xx/요청량 안전 제어
│   ├── config.py          # 환경변수 및 실행 설정
│   ├── response.py        # 성공·오류 응답 공통 판정
│   ├── security.py        # 민감정보 처리 지원
│   ├── token_manager.py   # 역할별 자동 로그인 및 토큰 관리
│   ├── course_api.py
│   └── legacy_course_api.py
├── conftest.py
├── requirements.txt
└── README.md
```

공통 생성 데이터 정리는 루트의 `test_support/cleanup.py`를 사용합니다.

## 3. 검증 범위

### 공통 인증·안전장치

-   역할별 인증 정보 처리
-   요청 Host 검증
-   상태 변경 요청 보호
-   요청 횟수 제한
-   timeout 및 제한적 네트워크 재시도
-   HTTP 5xx 발생 후 후속 요청 차단
-   응답 상태 판정 함수 검증
-   Cleanup Registry 동작 검증

### 클래스 홈

-   클래스 홈 데이터 조회
-   위젯/응답 필드 검증
-   인증·권한 조건 검증

### 학습 과목

-   과목 목록·상세 조회
-   학습 상태 및 수업 자료 조회
-   입력값·리소스 경계 검증
-   역할별 접근 제어
-   허용된 QA 데이터의 상태 변경 및 원복

### 수업 일정

-   학습자/교육자 조회 흐름
-   일정 관련 입력값 경계
-   인증·권한 조건

### 게시판

-   게시글 목록·상세 조회
-   검색·정렬
-   게시글 생성·첨부파일
-   게시글 수정
-   타 사용자·비밀글 등 권한 경계
-   잘못된 ID·입력값 검증

## 4. 설치

저장소 루트에서:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r api/requirements.txt
Copy-Item .env.example .env
```

실제 계정·비밀번호·토큰은 `.env` 또는 CI Credentials에만 설정합니다.

## 5. 인증 방식

역할별 이메일·비밀번호가 설정되어 있으면 Account API를 통해 자동
로그인을 시도하고 발급받은 토큰을 테스트 실행 중 사용합니다.

대표 역할:

-   학습자
-   교육자
-   타 학습자

자동 로그인 사용이 어려운 환경에서는 역할별 Token 환경변수를
fallback으로 사용할 수 있습니다.

민감정보는 저장소에 직접 기록하지 않으며 로그에서도 노출되지 않도록
처리합니다.

## 6. 테스트 실행

전체 API Suite:

``` powershell
.\.venv\Scripts\python.exe -m pytest api/tests -q -rs
```

기능별:

``` powershell
.\.venv\Scripts\python.exe -m pytest api/tests/classroom_home -q -rs
.\.venv\Scripts\python.exe -m pytest api/tests/course_list -q -rs
.\.venv\Scripts\python.exe -m pytest api/tests/class_schedule -q -rs
.\.venv\Scripts\python.exe -m pytest api/tests/board -q -rs
```

공통 안전장치만 확인:

``` powershell
.\.venv\Scripts\python.exe -m pytest api/tests/common_auth -q
```

Marker 예시:

``` powershell
python -m pytest api/tests -m read_only -q
python -m pytest api/tests -m learner -q
python -m pytest api/tests -m educator -q
python -m pytest api/tests -m boundary -q
```

Skip 사유는 `-rs` 옵션으로 확인합니다.

## 7. API 요청 안전장치

`api.utils.api_client`는 자동화가 잘못된 대상이나 위험한 조건으로
실행되는 것을 줄이기 위한 공통 제어를 담당합니다.

### 요청 횟수

기본 요청 상한은 `LXP_MAX_REQUESTS`이며 기본값은 2,000회입니다.

### 상태 변경 요청

POST/PATCH/DELETE 등 상태를 변경할 수 있는 요청은
`LXP_ALLOW_MUTATING_REQUESTS=true`만으로 무조건 실행되는 구조가 아니라
코드에서 명시적 확인 조건을 함께 요구합니다.

### 네트워크 오류와 5xx

네트워크 요청 실패는 설정된 범위에서 제한적으로 재시도할 수 있습니다.
반면 서버가 HTTP 5xx를 반환한 경우에는 자동 재시도하지 않고
`AbortTestError`로 후속 호출을 차단합니다.

### Host 검증

인증정보가 승인되지 않은 Host로 전달되지 않도록 대상 URL을 검증합니다.

## 8. 응답 판정

성공 여부를 HTTP 상태 하나로만 판단하지 않습니다.

일반 성공 응답은 다음 요소를 함께 확인할 수 있습니다.

-   HTTP 상태
-   `_result.status`
-   `_result.status_code`
-   필수 응답 데이터

Negative/권한 테스트는 여러 4xx를 한 번에 허용하지 않고 TC별 기대 오류를
구체적으로 지정합니다.

LXP API가 HTTP 200과 본문 내부 `fail` 상태를 함께 반환하는 경우 외부
HTTP 상태와 API 내부 논리 상태를 별도로 판정합니다.

세부 규칙은 [API 상태 코드 판정 기준](../docs/http-status-policy.md)을
참고합니다.

## 9. 데이터 Cleanup과 테스트 격리

상태 변경 테스트는 생성 또는 변경 직후 Cleanup Registry에 정리 작업을
등록합니다.

-   LIFO 순서로 정리
-   하나의 cleanup이 실패해도 나머지 cleanup 계속 수행
-   테스트가 직접 변경한 대상만 정리
-   원본 값이 필요한 수정 테스트는 실행 전 값을 저장한 뒤 복구
-   정리 경로가 확정되지 않은 상태 변경 테스트는 Skip

세부 기준은 [테스트 실행 순서와 상태 격리
기준](../docs/test-execution-isolation.md)을 참고합니다.

## 10. Allure · Google Sheets · Jira 연동

Jenkins API Job에서는 pytest 실행 후 다음 흐름으로 결과를 처리합니다.

``` text
pytest
  ↓
Allure Results
  ↓
결과 검사
  ↓
TC 매핑 검증
  ↓
Google Sheets 결과 반영
  ↓
실패 TC Jira 이슈 생성/재사용
```

관련 스크립트:

-   `scripts/inspect_allure_results.py`
-   `scripts/validate_allure_tc_mapping.py`
-   `scripts/update_api_tc_results.py`
-   `scripts/create_api_jira_issues.py`

테스트 코드와 TC 문서는 파일명·함수명 기반 매핑 정보를 사용해 결과를
연결합니다. rerun이 발생한 경우 최종 상태만 보고 최초 실패를 숨기지
않도록 attempt 이력을 함께 처리합니다.

## 11. Jenkins 실행

API CI는 루트의 `Jenkinsfile.api`를 사용합니다.

주요 단계:

1.  가상환경 생성
2.  `api/requirements.txt` 설치
3.  외부 연동 사전 검증
4.  `api/tests` 실행
5.  Allure/JUnit 결과 수집
6.  TC 매핑 검증
7.  Google Sheets 결과 업데이트
8.  실패 TC Jira 처리
9.  Discord 결과 알림

Jenkins Credentials에는 계정, 비밀번호, 서비스 계정, Jira 인증정보,
Discord Webhook 등 민감정보를 저장하고 코드에 직접 넣지 않습니다.

## 12. 개발 서버 종료 후 확인 가능한 항목

현재 원 프로젝트 Dev 환경이 종료되어 실제 API 회귀 실행은 불가능합니다.
저장소 리팩터링이나 포트폴리오 정리 후에는 다음 검증으로 코드 구조를
확인할 수 있습니다.

``` powershell
python -m compileall -q api performance scripts test_support
python -c "import api; import performance; import test_support; print('IMPORT OK')"
python -m pytest --collect-only -q
```

이 검증은 문법, import, pytest 수집 구조를 확인하지만 실제 API 계약이나
서버 상태를 재검증하는 것은 아닙니다.
