# Triple Q — LXP QA Automation

엘리스 LXP(Learning eXperience Platform)의 핵심 학습 흐름을 API, Selenium E2E, JMeter 성능 테스트로 검증하는 QA 자동화 프로젝트입니다. 이 저장소는 서비스 코드가 아니라 테스트 코드, 실행 안전장치, CI/CD 연동 및 결과 추적 도구를 관리합니다.

> 모든 테스트는 승인된 Dev 환경과 QA 전용 데이터에서만 실행합니다. 계정, 비밀번호, 토큰, 계정 CSV 및 내부 API 명세는 외부에 공유하거나 Git에 커밋하지 않습니다.

## 1. 자동화 범위

| Part | 도구 | 검증 범위 | 주요 경로 |
| --- | --- | --- | --- |
| Part 1 — API | pytest, requests | 정상·입력 검증·인증·권한 경계, 응답 계약 | `part1_api_automation/` |
| Part 2 — 성능 | Apache JMeter | 과목 조회 → 시험 입장 → 시작 → 제출·종료 → 재응시 | `part2_performance/` |
| Part 3 — E2E | pytest, Selenium | 클래스 홈 → 학습 과목 → 수업 일정 → 게시판 통합 흐름 | `part3_e2e/` |

기능 담당은 다음과 같습니다.

| 이름 | 담당 영역 |
| --- | --- |
| 강승완 | 프로젝트 통합, 공통 환경, CI/CD 기반, 학습 과목 |
| 이명종 | 수업 일정 |
| 이주휘 | 게시판 |
| 팀 공동 | 클래스 홈, 공통 모듈 및 통합 검증 |

## 2. 현재 프로젝트 구조

```text
triple-q-qa-final/
├── part1_api_automation/
│   ├── tests/
│   │   ├── common_auth/
│   │   ├── classroom_home/
│   │   ├── course_list/
│   │   ├── class_schedule/
│   │   └── board/
│   └── utils/                 # API client, 인증, 상태 판정, 마스킹
├── part2_performance/
│   ├── data/                  # 계정 CSV는 하위 .gitignore로 제외
│   ├── jmeter/                # lecture_test_cycle.jmx
│   ├── scripts/               # 실행, 요약, 비교 리포트
│   ├── tests/                 # 실행기 안전장치 단위 테스트
│   └── README.md
├── part3_e2e/
│   ├── fixtures/              # 브라우저, 로그인, 앱, 캡처, TC 결과
│   ├── pages/                 # Page Object
│   └── tests/
│       ├── e2e_integration/   # Jenkins 기준 통합 E2E
│       ├── integrated/        # 읽기 전용 전체 기능 흐름
│       ├── login/
│       └── course_list/
├── scripts/                   # Sheets·Jira·Allure·로컬 E2E 도구
├── test_support/              # 생성 데이터 cleanup registry
├── docs/                      # 판정 기준, 격리 정책, 트러블슈팅
├── Jenkinsfile.api
├── Jenkinsfile.e2e
├── conftest.py
├── pytest.ini
├── requirements.txt
└── .env.example
```

## 3. 로컬 환경 준비

로컬 개발 기준은 Python 3.11이며 Jenkins는 Agent의 `python3`로 가상환경을 구성합니다. E2E 실행에는 Chrome 또는 지원 브라우저가 필요하고, 성능 테스트에는 Java와 Apache JMeter 5.6.3이 추가로 필요합니다.

Windows PowerShell에서 저장소 루트로 이동한 뒤 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

API 또는 E2E만 실행한다면 해당 Part의 의존성만 설치할 수 있습니다.

```powershell
python -m pip install -r part1_api_automation/requirements.txt
python -m pip install -r part3_e2e/requirements.txt
```

### 환경변수 설정

실제 값은 [`.env.example`](.env.example)을 복사한 `.env`에만 입력합니다. 주요 범주는 다음과 같습니다.

| 범주 | 대표 변수 | 비고 |
| --- | --- | --- |
| 공통 대상 | `LXP_ORG_NAME_SHORT`, `LXP_CLASSROOM_ID` | 승인된 QA 대상만 사용 |
| 서비스 주소 | `LXP_API_BASE_URL`, `LXP_ACCOUNT_API_BASE_URL`, `LXP_WEB_BASE_URL` | `*.dev.elicer.io` HTTPS만 허용 |
| 로그인 계정 | `LXP_LEARNER_EMAIL`, `LXP_EDUCATOR_EMAIL`과 각 비밀번호 | Jenkins에서는 Credentials로 주입 |
| 테스트 데이터 | `LXP_COURSE_ID`, `LXP_LECTURE_ID`, `LXP_MATERIAL_QUIZ_ID` 등 | 계정마다 임의로 바꾸는 값이 아니라 공유 QA fixture ID |
| 상태 변경 허용 | `LXP_ALLOW_MUTATING_REQUESTS` | 기본값 `false` 유지 |
| 비가역 초기화 | `LXP_ALLOW_IRREVERSIBLE_TEST_RESET` | 일반 MR/회귀 실행에서는 `false` 유지 |
| 성능 테스트 | `LXP_PERF_ACCOUNT_CSV`, `JMETER_BIN` | 로컬 절대 경로 가능, Git 공유 금지 |

`.env`와 계정 CSV는 이미 Git 추적에서 제외됩니다. 설정 여부는 값 자체를 출력하지 말고 변수명과 빈 값 여부만 확인합니다.

API 인증은 역할별 이메일·비밀번호로 Account API 자동 로그인을 먼저 수행하고, 발급 토큰은 프로세스 메모리에만 보관합니다. 자동 로그인이 불가능할 때만 `LXP_LEARNER_TOKEN`, `LXP_EDUCATOR_TOKEN`, `LXP_OTHER_LEARNER_TOKEN`을 fallback으로 사용합니다. 이메일 Credential과 `LXP_LEARNER_USER_ID` 같은 사용자 ID는 반드시 같은 사용자를 가리켜야 하며, 로컬 값을 Jenkins에 그대로 복사하지 않습니다.

통합 E2E는 게시글·일정·과목·첨부파일 기준값도 필요합니다. Jenkins는 [`Jenkinsfile.e2e`](Jenkinsfile.e2e)의 환경 검증 목록을 사용하며, 로컬 실행자는 같은 변수들을 승인된 QA 데이터에 맞춰 설정해야 합니다. 일정 날짜 4개(`LXP_E2E_SCHEDULE_START`, `LXP_E2E_SCHEDULE_END`, `LXP_E2E_ALL_DAY_DATE`, `LXP_E2E_RECURRING_UNTIL`)는 `scripts/run_e2e_local.py`가 실행 시점 기준으로 자동 생성합니다.

## 4. 테스트 실행

모든 명령은 저장소 루트에서 실행합니다. `pytest.ini`가 기본 테스트 경로, 마커 및 `allure-results` 출력을 설정합니다.

### 4.1 API 자동화

전체 API 테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest part1_api_automation/tests -q -rs
```

기능별 실행 예시:

```powershell
.\.venv\Scripts\python.exe -m pytest part1_api_automation/tests/course_list -q -rs
.\.venv\Scripts\python.exe -m pytest part1_api_automation/tests/class_schedule -q -rs
.\.venv\Scripts\python.exe -m pytest part1_api_automation/tests/classroom_home -q -rs
.\.venv\Scripts\python.exe -m pytest part1_api_automation/tests/board -q -rs
```

환경변수 미설정이나 안전 플래그로 건너뛴 항목은 `-rs`에서 정확한 Skip 사유를 확인합니다. 조회 테스트만 선별하려면 `-m read_only`, 역할별로는 `-m learner` 또는 `-m educator`를 사용할 수 있습니다.

### 4.2 Selenium E2E

로그인 Smoke Test:

```powershell
.\.venv\Scripts\python.exe -m pytest part3_e2e/tests/login/test_login.py `
  -q -rs --selenium-browser chrome
```

Jenkins와 동일한 통합 E2E 대상:

```powershell
.\.venv\Scripts\python.exe -m pytest part3_e2e/tests/e2e_integration `
  -k independent -q -rs --selenium-browser chrome
```

브라우저 화면을 직접 보려면 `--selenium-headed`를 추가합니다. 로컬 HTML·Allure·JUnit 결과와 동적 일정 환경변수까지 한 번에 준비하려면 전용 실행기를 사용할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe scripts/run_e2e_local.py -k independent --headed
```

연속 도메인 흐름까지 확인하려면 `-k flow`를 사용합니다. Jenkins는 재현성과 TC 결과 집계를 위해 `-k independent`만 실행합니다.

> Allure의 pytest 실행 건수와 Google Sheets TC 수는 1:1이 아닙니다. 파라미터화된 pytest 항목 하나가 여러 TC Step을 기록할 수 있고, 독립 실행과 도메인 Flow도 서로 다른 집계 단위를 사용합니다.

Selenium은 설정된 드라이버, `PATH`, Selenium Manager 순으로 드라이버를 찾습니다. ChromeDriver를 직접 고정해야 하는 환경에서만 `LXP_CHROMEDRIVER_PATH`를 설정합니다.

### 4.3 JMeter 저부하 성능 테스트

성능 테스트는 승인된 시간에 팀 내 한 명만 실행합니다. 먼저 1명·1회 Smoke로 계정과 시나리오를 확인합니다.

```powershell
.\.venv\Scripts\python.exe -m part2_performance.scripts.run_lecture_load `
  --users 1 `
  --loops 1 `
  --rampup 1 `
  --accounts-csv "<QA 계정 CSV 절대 경로>" `
  --jmeter "<apache-jmeter-5.6.3\bin\jmeter.bat 절대 경로>" `
  --confirm-approved-window
```

본 테스트는 `5 → 10 → 20 → 30명`을 권장 순서로 진행하고, 5명 이상은 Ramp-up `90~120초`, 사용자별 Loop는 최대 3회로 제한합니다. 특정 단계만 재검증할 수 있으며 이전 단계 실행 여부를 코드가 강제하지는 않습니다.

설치, 본 테스트 명령, 기대 Sample 수, 판정 기준 및 결과 경로는 [Part 2 성능 테스트 안내](part2_performance/README.md)를 따릅니다.

## 5. 안전 설계와 판정 기준

### API

- 승인된 Dev HTTPS 호스트 외부로 인증정보가 전달되는 요청을 차단합니다.
- 요청마다 timeout과 호출 간 최소 대기를 적용하고, 네트워크 오류만 최대 1회 재시도합니다.
- API 테스트별 요청 상한은 기본 2,000회이며, 각 테스트 전후에 호출 수와 5xx 중단 상태를 초기화해 다음 테스트로 전파하지 않습니다.
- 5xx가 발생하면 현재 테스트의 추가 호출을 차단하고 서버 오류 유형을 기록합니다.
- 성공 응답은 HTTP 상태뿐 아니라 `_result.status`, `_result.status_code`와 필수 데이터까지 검증합니다.
- 오류 응답은 `4xx` 범위를 넓게 허용하지 않고 TC별 HTTP 상태, `fail_code`, 메시지를 구체적으로 판정합니다.
- 생성·수정 테스트는 `cleanup_registry`에 정리 작업을 등록하고 LIFO 순서로 삭제 또는 원복합니다. 일부 정리가 실패해도 나머지 정리를 계속 수행한 뒤 실패를 보고합니다.

세부 구현 기준은 [API 상태 코드 판정 기준](docs/http-status-policy.md)과 [테스트 실행 순서·상태 격리 기준](docs/test-execution-isolation.md)을 확인합니다.

### E2E

- 공통 로그인과 메뉴 이동은 session-scoped 인증 드라이버 및 AppShell fixture로 재사용합니다.
- Page Object에 화면 조작을 모으고 테스트에는 사용자 Journey와 기대 결과를 남깁니다.
- 변이 E2E는 `LXP_ALLOW_MUTATING_REQUESTS=true`인 승인 실행에서만 수행하며 생성 ID를 기준으로 정리합니다.
- 실패 스크린샷은 `LXP_CAPTURE_FAILURE_SCREENSHOTS=true`일 때 수집합니다. Jenkins 기본값은 실행 비용을 줄이기 위해 `false`입니다.
- TC 결과는 `artifacts/tc-results/tc_results.jsonl`로 수집하며, 실패 후 재실행 성공만으로 최초 실패를 숨기지 않습니다.

### 성능

- 각 Virtual User는 CSV 계정 하나를 스레드당 한 번 할당받고 동일 계정으로 모든 Loop를 수행합니다.
- 각 동작 사이 Uniform Random Timer 3~5초를 적용합니다.
- Sampler 실패 또는 HTTP 5xx 발생 시 즉시 전체 테스트를 중단합니다.
- HTTP 요청 timeout은 60초이고, 평균 시나리오 Latency 5,000ms 이상 또는 Error Rate 1% 이상은 실행 종료 후 FAIL로 판정합니다.
- 기대 `users × loops` 호출 수 또는 고유 스레드 수가 부족하면 성공률과 관계없이 INVALID입니다.
- Thread Group 540초, 실행기 600초는 단일 실행 안전 제한입니다. 전체 단계 합계 10분 제한은 운영자가 별도로 관리합니다.

## 6. CI/CD와 결과 연동

브랜치 운영은 `feature/* → develop → main` 흐름을 사용합니다. Merge Request와 GitLab Webhook을 통해 Jenkins의 API/E2E Job을 분리 실행합니다.

| 항목 | API Job | E2E Job |
| --- | --- | --- |
| Pipeline | `Jenkinsfile.api` | `Jenkinsfile.e2e` |
| 실행 대상 | `part1_api_automation/tests` | `part3_e2e/tests/e2e_integration -k independent` |
| Allure 원본 | `allure-results/api` | `allure-results/e2e` |
| JUnit | `pytest-results/api.xml` | `pytest-results/e2e.xml` |
| Google Sheets | TC 매핑 검증 후 결과 반영 | Collector 완전성 검증 후 결과 반영 |
| Jira | 실패 API TC 이슈 생성·재사용 | 실패 E2E 후보 Dry-run |
| 추가 결과 | Discord 알림 | 실패 캡처 archive, Discord 알림 |

계정·비밀번호·토큰·Webhook URL·Sheets 서비스 계정·Jira 자격증명은 Jenkins Credentials로 주입합니다. Secret 값을 Jenkinsfile, 콘솔 로그 또는 Allure 첨부에 직접 출력하지 않습니다.

현재 API Job은 비가역 초기화를 `false`로 유지합니다. E2E Job은 승인된 전용 응시 데이터 정리를 위해 `true`를 주입하므로, 이 설정을 다른 Job이나 공용 데이터 실행에 그대로 복사하지 않습니다.

```text
GitLab MR/Webhook
        ├── API Job → pytest → Allure/Sheets/Jira → Discord
        └── E2E Job → Selenium → Allure/Sheets/Jira Dry-run → Discord
```

## 7. 자주 발생하는 문제

### 테스트가 Skip되는 경우

```powershell
.\.venv\Scripts\python.exe -m pytest <테스트 경로> -q -rs
```

출력된 환경변수명, 역할 계정, 테스트 데이터 ID 또는 안전 플래그를 [`.env.example`](.env.example)과 대조합니다. 권한이나 전용 테스트 데이터가 없는 TC는 임의 값으로 우회하지 않습니다.

### `.pytest_cache` 접근 거부 경고

캐시가 필요 없는 일회성 실행은 다음처럼 수행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pytest <테스트 경로> -q -p no:cacheprovider
```

### Python 패키지를 찾지 못하는 경우

활성화된 가상환경과 테스트 실행 Python이 같은지 확인합니다.

```powershell
Get-Command python
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### JMeter 또는 계정 CSV를 찾지 못하는 경우

`--jmeter`와 `--accounts-csv`에는 파일 자체의 정확한 경로를 전달합니다. 두 값을 각각 `JMETER_BIN`, `LXP_PERF_ACCOUNT_CSV`에 저장할 수도 있습니다. CSV에는 `login_id,password` 헤더와 필요한 수의 고유 QA 계정이 있어야 합니다.

## 8. 테스트 작성 및 협업 규칙

1. 함수명과 docstring에는 누가, 무엇을, 왜 검증하는지가 드러나야 합니다.
2. HTTP 상태 코드만 보지 않고 응답 계약, 데이터 격리, 권한 및 원복 여부를 함께 확인합니다.
3. 테스트 간 순서 의존성을 만들지 않고, 생성 데이터는 성공·실패와 관계없이 정리합니다.
4. 작업 전 `develop` 최신 변경을 받고 기능 브랜치에서 작업한 뒤 Merge Request로 리뷰합니다.
5. 제품 결함은 재현 절차, 기대·실제 결과, 증적, 심각도를 포함해 Jira에 기록합니다.
6. 테스트 코드, 로그, 리포트에는 토큰·비밀번호·개인정보·서명 URL을 남기지 않습니다.

## 9. 관련 문서

- [Part 2 시험 응시 저부하 성능 테스트](part2_performance/README.md)
- [API 상태 코드 판정 기준](docs/http-status-policy.md)
- [테스트 실행 순서와 상태 격리 기준](docs/test-execution-isolation.md)
- [E2E 테스트 트러블슈팅 및 제외 범위](docs/e2e-troubleshooting-report.md)
- [환경변수 템플릿](.env.example)

내부 API 명세와 계정 자료는 승인된 팀 저장소 안에서만 사용하며 README나 외부 결과보고서에 원문을 첨부하지 않습니다.
