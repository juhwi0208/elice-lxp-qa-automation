# Elice LXP QA Automation

엘리스 LXP(Learning eXperience Platform)의 핵심 기능을 대상으로 **API
자동화 테스트와 JMeter 저부하 성능 테스트를 구축하고, Jenkins 기반 CI와
Google Sheets·Jira·Discord 결과 관리까지 연결한 QA 자동화
프로젝트**입니다.

이 저장소는 서비스 애플리케이션 코드가 아니라 테스트 코드, 실행
안전장치, 결과 판정 및 결함 추적 자동화 도구를 관리합니다.

> 테스트는 승인된 QA/Dev 환경과 전용 테스트 데이터에서만 실행하도록
> 설계했습니다. 계정, 비밀번호, 토큰, 계정 CSV, 서비스 계정 키 등
> 민감정보는 Git에 커밋하지 않습니다. 원 프로젝트의 Dev 환경은
> 종료되었으므로 현재 재실행하려면 별도의 승인된 테스트 환경과 유효한
> 테스트 데이터가 필요합니다.

## 1. 프로젝트 개요

### 목표

-   학습자·교육자 관점의 핵심 API 기능과 역할별 권한을 반복 검증
-   입력값·경계값·인증·권한 오류를 정상 응답과 구분하여 검증
-   상태 변경 테스트의 데이터 잔류와 테스트 간 간섭 최소화
-   잘못된 환경·과도한 요청·서버 장애 상황에서 자동화를 안전하게 중단
-   JMeter 저부하 테스트로 사용자 증가에 따른 Latency, Throughput, Error
    Rate 변화 확인
-   Jenkins 실행 결과를 Allure, Google Sheets, Jira, Discord와 연결해
    결과 기록과 결함 추적 자동화

### 자동화 범위

  -----------------------------------------------------------------------
  영역                    기술                    주요 검증
  ----------------------- ----------------------- -----------------------
  API Automation          Python, pytest,         정상 기능, 입력 검증,
                          requests                인증·권한 경계, 응답
                                                  계약, 데이터 원복

  Performance Test        Apache JMeter, Python   시험 응시 사이클, 실행
                                                  완전성, Latency,
                                                  P95/P99, Throughput,
                                                  Error Rate

  CI / Result Management  Jenkins, Allure, Google 테스트 실행, 결과 수집,
                          Sheets, Jira, Discord   TC 매핑, 실패 이슈
                                                  연결, 알림
  -----------------------------------------------------------------------

API 기능 범위는 클래스 홈, 학습 과목, 수업 일정, 게시판을 중심으로
구성되어 있습니다.

## 2. 프로젝트 특징

### API 테스트 안전장치

단순히 API를 호출하고 상태 코드만 확인하지 않습니다.

-   승인된 QA API Host 검증
-   상태 변경 요청은 `LXP_ALLOW_MUTATING_REQUESTS=true`와 명시적 확인이
    함께 있어야 실행
-   요청 횟수 상한과 호출 간격 적용
-   네트워크 오류만 제한적으로 재시도
-   HTTP 5xx 발생 시 `AbortTestError`로 이후 요청 차단
-   인증정보와 민감정보 로그 마스킹
-   생성·수정 데이터는 Cleanup Registry에 등록해 역순 정리
-   HTTP 상태와 API 내부 `_result.status`, `status_code`, `fail_code`를
    구분하여 판정

### 부하테스트 실행 신뢰성

JMeter 실행 자체가 끝났다는 이유만으로 PASS로 판정하지 않습니다.

-   허용 User: 1명 Smoke 또는 5/10/20/30명
-   Loop 최대 3회
-   5명 이상 Ramp-up 90\~120초
-   Thread별 CSV 계정 1회 할당 후 모든 Loop에서 동일 계정 사용
-   사용자 행동 사이 3\~5초 Random Timer
-   Sampler 실패 또는 HTTP 5xx 발생 시 즉시 중단
-   기대 `users × loops` 호출 수와 고유 Thread 수를 검증
-   실행량 미충족 시 성능 수치와 관계없이 `INVALID`
-   실행 완전성 충족 후 Error Rate와 Average Latency 기준으로 PASS/FAIL
    판정

## 3. 프로젝트 구조

``` text
elice-lxp-qa-automation/
├── api/
│   ├── tests/
│   │   ├── common_auth/
│   │   ├── classroom_home/
│   │   ├── course_list/
│   │   ├── class_schedule/
│   │   └── board/
│   ├── utils/
│   ├── conftest.py
│   ├── requirements.txt
│   └── README.md
├── performance/
│   ├── data/
│   ├── jmeter/
│   │   └── lecture_test_cycle.jmx
│   ├── scripts/
│   ├── tests/
│   └── README.md
├── scripts/
│   ├── inspect_allure_results.py
│   ├── validate_allure_tc_mapping.py
│   ├── update_api_tc_results.py
│   ├── create_api_jira_issues.py
│   └── ...
├── test_support/
│   └── cleanup.py
├── docs/
│   ├── http-status-policy.md
│   └── test-execution-isolation.md
├── Jenkinsfile.api
├── discord_notify.py
├── conftest.py
├── pytest.ini
├── requirements.txt
└── .env.example
```

## 4. 로컬 환경 준비

기준 Python 버전은 3.11입니다. 성능 테스트에는 Java와 Apache JMeter
5.6.3이 추가로 필요합니다.

Windows PowerShell:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

API 의존성만 설치할 경우:

``` powershell
python -m pip install -r api/requirements.txt
```

### 주요 환경변수

실제 값은 `.env.example`을 복사한 `.env` 또는 Jenkins Credentials에
설정합니다.

  -------------------------------------------------------------------------------------
  범주                    대표 변수                             용도
  ----------------------- ------------------------------------- -----------------------
  공통 대상               `LXP_ORG_NAME_SHORT`,                 QA 기관·클래스 식별
                          `LXP_CLASSROOM_ID`                    

  API 주소                `LXP_API_BASE_URL`,                   API 호출 및 자동 로그인
                          `LXP_ACCOUNT_API_BASE_URL`            

  역할별 계정             `LXP_LEARNER_EMAIL`,                  역할별 토큰 자동 발급
                          `LXP_EDUCATOR_EMAIL`,                 
                          `LXP_OTHER_LEARNER_EMAIL`             

  Fallback Token          `LXP_LEARNER_TOKEN`,                  자동 로그인 실패 시
                          `LXP_EDUCATOR_TOKEN`,                 선택적 사용
                          `LXP_OTHER_LEARNER_TOKEN`             

  테스트 데이터           `LXP_COURSE_ID`, `LXP_LECTURE_ID`,    기능별 QA Fixture
                          `LXP_MATERIAL_QUIZ_ID` 등             

  상태 변경 허용          `LXP_ALLOW_MUTATING_REQUESTS`         POST/PATCH/DELETE 안전
                                                                제어

  비가역 초기화           `LXP_ALLOW_IRREVERSIBLE_TEST_RESET`   응시 기록 초기화 등
                                                                별도 허용

  성능 테스트             `LXP_PERF_ACCOUNT_CSV`, `JMETER_BIN`  QA 계정 CSV와 JMeter
                                                                경로
  -------------------------------------------------------------------------------------

민감정보 값 자체를 로그에 출력하지 않습니다.

## 5. API 자동화

상세 구조와 실행 방법은 [API 자동화 README](api/README.md)를 참고합니다.

전체 API 테스트:

``` powershell
.\.venv\Scripts\python.exe -m pytest api/tests -q -rs
```

기능별 실행:

``` powershell
.\.venv\Scripts\python.exe -m pytest api/tests/classroom_home -q -rs
.\.venv\Scripts\python.exe -m pytest api/tests/course_list -q -rs
.\.venv\Scripts\python.exe -m pytest api/tests/class_schedule -q -rs
.\.venv\Scripts\python.exe -m pytest api/tests/board -q -rs
```

조회 테스트만 선별하려면 `-m read_only`, 역할별 검증은 `-m learner`,
`-m educator`를 사용할 수 있습니다. 환경변수 또는 안전 조건이 충족되지
않아 Skip된 항목은 `-rs`로 사유를 확인합니다.

API 오류 판정 규칙은 [HTTP 상태 코드 판정
기준](docs/http-status-policy.md), 데이터 격리 원칙은 [테스트 실행
순서와 상태 격리 기준](docs/test-execution-isolation.md)을 따릅니다.

## 6. JMeter 저부하 성능 테스트

상세 실행 절차와 결과 판정은 [성능 테스트
README](performance/README.md)를 참고합니다.

오프라인 안전장치 테스트:

``` powershell
.\.venv\Scripts\python.exe -m pytest performance/tests -q -p no:cacheprovider
```

1 User Smoke 예시:

``` powershell
.\.venv\Scripts\python.exe -m performance.scripts.run_lecture_load `
  --users 1 `
  --loops 1 `
  --rampup 1 `
  --accounts-csv "<QA 계정 CSV 경로>" `
  --jmeter "<JMeter 실행 파일 경로>" `
  --confirm-approved-window
```

본 테스트는 5/10/20/30 User 중 필요한 부하 단계를 실행할 수 있으며, 이전
단계 실행 여부를 코드가 강제하지 않습니다.

## 7. 결과 판정과 안전 정책

### API

-   일반 성공 응답은 HTTP 상태와 API 내부 상태를 함께 확인
-   Negative/권한 TC는 여러 4xx를 포괄적으로 허용하지 않고 TC별 기대
    상태를 명시
-   5xx는 정상 Negative 결과가 아니라 서버 오류로 분리
-   요청 횟수 상한 기본값은 2,000회
-   요청 간 최소 간격과 timeout 적용
-   네트워크 오류만 최대 1회 재시도
-   상태 변경 요청은 별도 안전 플래그 필요
-   생성·수정 데이터는 Cleanup Registry로 정리

### Performance

실행 완전성이 우선입니다.

1.  기대 Sample 및 Thread 실행량 충족 여부 확인
2.  미충족 시 `INVALID`
3.  완전성 충족 후 Scenario API 기준으로 성능 판정
    -   Average Latency `< 5,000ms`
    -   Error Rate `< 1%`

P95/P99 Latency, Response Time, TPS/Throughput은 사용자 증가에 따른 변화
분석 지표로 함께 수집합니다.

## 8. Jenkins CI 및 결과 관리

API 자동화는 `Jenkinsfile.api`를 기준으로 실행합니다.

``` text
GitLab
  ↓
Jenkins API Job
  ↓
pytest
  ↓
Allure Results
  ↓
TC 매핑 검증
  ↓
Google Sheets 결과 반영
  ↓
실패 TC Jira 이슈 생성/연결
  ↓
Discord 결과 알림
```

주요 처리 흐름:

1.  Python 가상환경 및 API 의존성 설치
2.  Google Sheets/Jira 연결 상태 및 Jira 필드 검증
3.  `api/tests` 실행 및 Allure/JUnit 결과 생성
4.  Allure 결과 검사
5.  테스트 함수와 TC 매핑 검증
6.  Google Sheets에 API TC 결과 반영
7.  실패 TC를 Jira 이슈 후보로 처리하고 기존 이슈가 있으면 재사용
8.  최종 결과를 Discord로 알림

Jenkins에서는 계정·비밀번호·토큰·Webhook URL·Google 서비스 계정·Jira
자격증명을 Credentials로 주입하며 저장소에 직접 저장하지 않습니다.

## 9. 테스트 결과 관리 원칙

-   pytest 실행 건수와 문서의 TC 수는 동일 개념으로 사용하지 않습니다.
-   Allure 결과에서 테스트 상태를 수집하고 TC 매핑 검증 후 Google
    Sheets에 반영합니다.
-   rerun이 발생한 경우 최초 실패 이력을 숨기지 않고 attempt 정보를 함께
    분석합니다.
-   실패 결과는 제품 결함, 테스트 코드 문제, 테스트 데이터·환경 제약을
    구분하여 확인합니다.
-   Jira 이슈에는 재현 조건, 기대 결과, 실제 결과와 실패 증적을
    연결합니다.

## 10. 테스트 작성 및 협업 규칙

1.  테스트 함수와 docstring에서 검증 대상과 목적이 드러나게 작성합니다.
2.  HTTP 상태만 확인하지 않고 응답 계약, 역할별 권한, 데이터 상태를 함께
    검증합니다.
3.  다른 TC의 실행 결과에 의존하지 않습니다.
4.  생성·수정 데이터는 성공·실패와 관계없이 정리할 수 있도록 구성합니다.
5.  테스트 코드와 로그에 토큰·비밀번호·개인정보를 남기지 않습니다.
6.  제품 결함은 재현 조건과 기대·실제 결과를 구분해 기록합니다.

## 11. 관련 문서

-   [API 자동화 안내](api/README.md)
-   [성능 테스트 안내](performance/README.md)
-   [API 상태 코드 판정 기준](docs/http-status-policy.md)
-   [테스트 실행 순서와 상태 격리
    기준](docs/test-execution-isolation.md)
-   [환경변수 템플릿](.env.example)

내부 API 명세와 실제 QA 계정 자료는 승인된 저장소와 실행 환경 안에서만
관리합니다.
