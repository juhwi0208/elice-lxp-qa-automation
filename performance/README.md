# 시험 응시 저부하 성능 테스트 --- JMeter

`performance/`는 시험 응시 흐름을 대상으로 **허용된 저부하 조건에서
사용자 증가에 따른 성능 변화를 확인하고, 실행 완전성과 안전 조건을 자동
검증하는 테스트 모듈**입니다.

원 프로젝트에서는 사전 승인된 Dev 환경과 QA 전용 계정으로 실행했습니다.
현재 해당 Dev 환경이 종료되었으므로 재실행하려면 코드의 승인 대상과
테스트 데이터를 새로운 승인 환경에 맞게 검토해야 합니다.

## 1. 테스트 목적

-   사용자 증가에 따른 Average/P95/P99 Latency 변화 확인
-   TPS/Throughput 변화 확인
-   Error Rate 및 HTTP 5xx 발생 여부 확인
-   설정한 User × Loop가 실제로 끝까지 수행되었는지 검증
-   불완전한 실행을 성능 PASS로 오판하지 않도록 `INVALID` 상태 분리
-   잘못된 대상·과도한 User/Loop/Ramp-up 설정을 실행 전에 차단

## 2. 디렉터리 구조

``` text
performance/
├── data/                         # QA 계정 CSV 위치, 실제 CSV는 Git 제외
├── jmeter/
│   └── lecture_test_cycle.jmx    # 시험 응시 JMeter 시나리오
├── scripts/
│   ├── run_lecture_load.py       # 실행 전 검증 + JMeter 실행
│   ├── summarize_results.py      # JTL/HTML 결과 판정 및 요약
│   └── build_comparison_report.py
├── tests/
│   └── test_lecture_load_safety.py
└── README.md
```

## 3. 사전 준비

-   Python 프로젝트 가상환경
-   Java
-   Apache JMeter 5.6.3
-   실행 User 수 이상의 고유 QA 계정
-   승인된 테스트 환경과 시험 데이터

계정 CSV 형식:

``` text
login_id,password
```

계정 CSV는 Git에 커밋하지 않습니다.

JMeter 경로와 계정 CSV는 CLI 인자 또는 환경변수로 전달할 수 있습니다.

-   `JMETER_BIN`
-   `LXP_PERF_ACCOUNT_CSV`

## 4. 시험 응시 시나리오

각 Virtual User는 CSV에서 서로 다른 계정 하나를 할당받아 로그인하고,
같은 계정으로 모든 Loop를 수행합니다.

1.  과목 조회
2.  시험 입장
3.  시험 시작
4.  시험 제출·종료
5.  재응시 초기화

시나리오 API 사이에는 Uniform Random Timer `3~5초`를 적용합니다.

``` text
course
  ↓ 3~5s
enter
  ↓ 3~5s
start
  ↓ 3~5s
stop
  ↓ 3~5s
reset
```

## 5. 실행 전 안전검증

`run_lecture_load.py`와 JMX 양쪽에서 주요 제한을 확인합니다.

  항목                    기준
  ----------------------- ----------------------------
  허용 User               `1`, `5`, `10`, `20`, `30`
  1 User                  Smoke Test 용도
  Loop                    `1~3`
  5명 이상 Ramp-up        `90~120초`
  1 User Ramp-up          `1~120초`
  행동 간 Timer           `3~5초`
  HTTP Response Timeout   `60,000ms`
  Thread Group Duration   `540초`
  실행 프로세스 제한      `600초`
  Sampler 실패            전체 테스트 즉시 중단
  HTTP 5xx                즉시 중단 및 보고

실행기는 승인된 대상 URL과 ID, JMX 구조, Timer, timeout, Thread/Loop
속성 연결 등을 확인합니다. 환경변수만 바꿔 승인 대상 검증을 우회하는
용도로 사용하지 않습니다.

## 6. 오프라인 안전장치 테스트

실제 부하를 발생시키지 않고 실행기 제한과 JMX 안전설정을 확인합니다.

``` powershell
.\.venv\Scripts\python.exe -m pytest performance/tests -q -p no:cacheprovider
```

## 7. Smoke Test

실제 본 테스트 전에는 1 User로 요청 흐름과 계정 조건을 확인합니다.

``` powershell
python -m performance.scripts.run_lecture_load `
  --users 1 `
  --loops 1 `
  --rampup 1 `
  --accounts-csv "<QA 계정 CSV 경로>" `
  --jmeter "<apache-jmeter-5.6.3\bin\jmeter.bat 경로>" `
  --confirm-approved-window
```

## 8. 본 테스트

원 프로젝트의 저부하 검증 범위는 5/10/20/30 User였습니다.

``` powershell
python -m performance.scripts.run_lecture_load `
  --users 5 `
  --loops 3 `
  --rampup 90 `
  --accounts-csv "<QA 계정 CSV 경로>" `
  --jmeter "<apache-jmeter-5.6.3\bin\jmeter.bat 경로>" `
  --confirm-approved-window
```

`--users`를 10, 20, 30으로 변경해 필요한 부하 구간을 실행할 수 있습니다.
사용자 증가 순서로 실행하는 것을 권장할 수 있지만, 실행기는 이전 단계
완료 여부를 강제하지 않습니다.

## 9. 실행 완전성 검증

각 시나리오 API의 기대 호출 수는 `users × loops`입니다.

전체 JTL에는 Thread별 1회 수행되는 Safety Guard와 Login도 포함됩니다.

  Users × Loops     API당 기대 호출   전체 JTL Sample
  --------------- ----------------- -----------------
  1 × 1                           1                 7
  1 × 3                           3                17
  5 × 3                          15                85
  10 × 3                         30               170
  20 × 3                         60               340
  30 × 3                         90               510

전체 Sample 계산:

``` text
users × (Safety Guard 1 + Login 1 + 시나리오 API 5 × loops)
```

설정한 User/Loop 실행량 또는 고유 Thread 수가 충족되지 않으면 결과는
`INVALID`입니다. Error Rate가 낮더라도 불완전한 실행을 PASS로 판정하지
않습니다.

## 10. 성능 판정 기준

실행 완전성을 충족한 결과에 대해 시나리오 API Sample을 기준으로
판정합니다.

-   Average Latency `< 5,000ms`
-   Error Rate `< 1%`

즉 다음과 같이 구분합니다.

  -----------------------------------------------------------------------
  상태                                판정
  ----------------------------------- -----------------------------------
  `PASS`                              실행 완전성 충족 + Error Rate \<
                                      1% + Average Latency \< 5,000ms

  `FAIL`                              실행은 완전하지만 성능 기준 미충족

  `INVALID`                           기대 User/Loop/Sample/Thread 실행량
                                      미충족
  -----------------------------------------------------------------------

P95/P99 Latency, Response Time, TPS/Throughput은 PASS/FAIL 단일 기준이
아니라 사용자 증가에 따른 성능 변화와 병목 후보를 분석하기 위한 지표로
함께 수집합니다.

HTTP Response Timeout 60초와 성능 목표 Average Latency 5초는 서로 다른
기준입니다.

## 11. 결과 파일

각 실행은 다음 구조로 결과를 저장합니다.

``` text
performance/results/lecture-cycle-<users>u-<loops>loop-<timestamp>/
├── samples.jtl
├── jmeter.log
├── run_meta.json
└── report/
    ├── index.html
    ├── statistics.json
    ├── summary.html
    ├── summary.json
    ├── summary.csv
    └── transactions.csv
```

JMeter HTML Dashboard는 원본 리포트로 유지하고 `summary.html`과
`summary.json`은 자동 판정·요약 결과로 사용합니다.

## 12. 여러 실행 비교

``` powershell
python -m performance.scripts.build_comparison_report
```

생성 결과:

``` text
performance/results/comparison/
├── comparison.csv
└── comparison.html
```

비교 리포트에서는 실행별 Average/P95/P99 Latency, Response Time,
TPS/Throughput, Error Rate를 비교해 User 증가에 따른 추세와 변곡점
후보를 확인합니다.

## 13. 재실행 시 주의사항

현재 원 프로젝트의 Dev 환경은 종료된 상태입니다. 따라서 이 저장소를
포트폴리오 또는 참고 코드로 실행할 때 기존 URL과 QA 데이터 ID를 그대로
사용하지 않습니다.

새 환경에서 재사용하려면 다음을 먼저 검토해야 합니다.

1.  승인된 Host와 테스트 대상 ID
2.  시험 응시·재응시 API 계약
3.  QA 전용 계정 CSV
4.  초기화가 다른 사용자 데이터에 영향을 주지 않는지
5.  `run_lecture_load.py`의 승인 대상 allowlist
6.  JMX의 API 경로와 테스트 데이터
7.  부하 실행에 대한 운영 승인
