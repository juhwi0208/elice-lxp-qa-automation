# Part 2 — 시험 응시 저부하 성능 테스트 (JMeter)

QA6 Part2에서 사전 승인된 **Dev 환경**을 대상으로 저부하 성능 테스트를 수행합니다. Production에서는 실행하지 않습니다.

## 테스트 대상

- Web: `https://dev-qatrack-web.dev.elicer.io/classrooms/28f79a10-c14b-4531-9feb-53d9a5c157fc/courses/727/lectures/1581`
- API: `https://dev-qatrack-api.dev.elicer.io`
- Account API: `https://dev-qatrack-account-api.dev.elicer.io/login/pw`
- org: `academy`
- course_id: `727`
- lecture_id: `1581`
- lecture_page_id: `1327`

## 사전 준비

- Java가 설치되어 `java -version`이 정상 동작해야 합니다.
- Apache JMeter 5.6.3을 내려받아 압축을 해제합니다.
- QA 계정 CSV는 `login_id,password` 헤더와 실행 User 수 이상의 고유 계정을 가져야 합니다.
- 실제 계정 CSV는 `part2_performance/data/.gitignore`의 `*.csv` 규칙으로 Git 추적에서 제외됩니다.
- 모든 명령은 저장소 루트에서 실행합니다.

JMeter 실행 파일은 `--jmeter` 인자로 전달하거나 `.env`의 `JMETER_BIN`에 설정할 수 있습니다. 계정 CSV도 `--accounts-csv`를 사용하며, 개인 PC마다 실제 절대 경로가 다를 수 있습니다.

실제 부하를 발생시키기 전에 오프라인 안전장치 테스트를 확인합니다.

```powershell
.\.venv\Scripts\python.exe -m pytest part2_performance/tests -q -p no:cacheprovider
```

## 시험 응시 시나리오

각 Virtual User는 서로 다른 테스트 계정으로 로그인한 뒤 다음 사이클을 수행합니다.

1. `GET /org/academy/course/get/?course_id=727`
2. `POST /org/academy/user/lecture/test/enter/` (`lecture_id=1581`)
3. `POST /org/academy/user/lecture/test/start/` (`lecture_id=1581`)
4. `POST /org/academy/user/lecture/test/stop/` (`lecture_id=1581`)
5. `POST /org/academy/lecture/test/reset/by_self/` (`lecture_id=1581`)

동작 사이에는 Uniform Random Timer `3~5초`를 적용합니다.

`course → 3~5초 → enter → 3~5초 → start → 3~5초 → stop → 3~5초 → reset`

## 실행 기준

- 도구: Apache JMeter 5.6.3
- 환경: Dev only
- 본 테스트 Users: `5`, `10`, `20`, `30`
- 권장 진행: `5 → 10 → 20 → 30`
- 특정 단계의 재검증이 필요한 경우 해당 단계만 다시 실행할 수 있으며, 코드에서 이전 단계 실행 여부를 강제하지 않습니다.
- Loop Count: 최대 `3`
- Infinite Loop 금지
- 5명 이상 Ramp-up: `90~120초` (기본 `90초`)
- 1 User Smoke는 Ramp-up `1초` 허용
- 사용자 행동 간 Timer: `3~5초`, 총 4개
- ThreadGroup 안전 제한: `540초`
- 실행 프로세스 제한: `600초`
- `ThreadGroup.on_sample_error=stoptestnow`
- HTTP 5xx 발생 시 즉시 중단 및 보고
- HTTP Response Timeout: `60,000ms`
- 승인된 시간에 팀 내 1명만 실행

## 테스트 계정

CSV 형식은 정확히 다음과 같습니다.

```text
login_id,password
```

30개 이상의 서로 다른 테스트 계정을 준비하며 실제 CSV는 Git에 커밋하지 않습니다. 각 Thread는 계정 하나를 한 번 할당받아 동일 계정으로 모든 Loop를 수행합니다.

## Smoke Test

본 테스트 전 요청 흐름을 확인할 때:

```powershell
python -m part2_performance.scripts.run_lecture_load `
  --users 1 `
  --loops 1 `
  --rampup 1 `
  --accounts-csv ".\part2_performance\data\QA6test_account_list_(30)_3.csv" `
  --jmeter "C:\apache-jmeter-5.6.3\bin\jmeter.bat" `
  --confirm-approved-window
```

## 본 테스트

승인된 시간에 필요한 단계를 실행합니다. 권장 순서는 5 → 10 → 20 → 30입니다.

```powershell
python -m part2_performance.scripts.run_lecture_load `
  --users 5 `
  --loops 3 `
  --rampup 90 `
  --accounts-csv ".\part2_performance\data\QA6test_account_list_(30)_3.csv" `
  --jmeter "C:\apache-jmeter-5.6.3\bin\jmeter.bat" `
  --confirm-approved-window
```

`--users`를 필요에 따라 `10`, `20`, `30`으로 변경합니다.

## 실행 완전성 확인

각 시나리오 API의 기대 호출 수는 `users × loops`입니다. 1명·1회 Smoke의 전체 기대 Sample은 7건입니다.

| Users × Loops | API당 기대 호출 | 전체 JTL Sample* |
|---|---:|---:|
| 1 × 1 | 1 | 7 |
| 1 × 3 | 3 | 17 |
| 5 × 3 | 15 | 85 |
| 10 × 3 | 30 | 170 |
| 20 × 3 | 60 | 340 |
| 30 × 3 | 90 | 510 |

\* 전체 Sample = `users × (Safety Guard 1 + Login 1 + 시나리오 API 5 × loops)`

설정한 User/Loop 실행량이 충족되지 않으면 결과는 `INVALID`로 처리합니다.

## 성능 판정 기준

실행 완전성을 충족한 결과에 대해:

- Average Latency `< 5,000ms`
- Error Rate `< 1%`

HTTP Response Timeout `60,000ms`와 성능 목표 Latency `5,000ms`는 서로 다른 기준입니다.

분석 지표는 Average Latency, P95/P99 Latency, Response Time, TPS/Throughput, Error Rate를 사용합니다.

성능 PASS/FAIL 지표는 Safety Guard와 Login을 제외한 5개 시나리오 API Sample로 계산합니다. 전체 JTL Sample 수에는 Safety Guard와 Login이 포함되므로 두 집계 수는 일치하지 않습니다.

실행기는 PASS일 때 종료 코드 `0`, FAIL 또는 INVALID일 때 종료 코드 `2`를 반환합니다. Sampler 실패·비정상 API 응답·HTTP 5xx는 JMeter 실행 중 즉시 중단 대상이고, 평균 Latency 5,000ms 기준은 실행 완료 후 결과 판정에 사용합니다.

## 결과 및 비교 리포트

각 실행 결과는 다음 형태로 저장됩니다.

```text
part2_performance/results/lecture-cycle-<users>u-<loops>loop-<timestamp>/
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

여러 실행 결과 비교:

```powershell
python -m part2_performance.scripts.build_comparison_report
```

생성 결과:

```text
part2_performance/results/comparison/
├── comparison.csv
└── comparison.html
```

비교 리포트에서는 실행별 Average/P95/P99 Latency, Response Time, TPS, Error Rate를 비교하여 사용자 증가에 따른 성능 변화와 병목/변곡점 후보를 분석합니다.

JMeter HTML Dashboard를 원본 성능 리포트로 유지하고 `summary.html` 및 `comparison.html`을 요약·보고용으로 사용합니다.
