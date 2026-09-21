# API 상태 코드 판정 기준

API 테스트는 여러 오류 상태를 한 번에 허용하지 않는다. 각 TC는 아래 기준에 따라
HTTP 상태 코드 하나를 기대값으로 지정하고, 실제 값이 다르면 실패시킨다.

| 상태 | 사용 기준 |
| --- | --- |
| 400 Bad Request | 필수값 누락, 형식·타입·길이 오류 등 잘못된 요청 |
| 401 Unauthorized | 로그인 정보 없음, 만료·위조된 인증 정보 |
| 403 Forbidden | 인증은 되었지만 역할 또는 리소스 접근 권한 없음 |
| 404 Not Found | 존재하지 않거나 삭제된 리소스 |
| 409 Conflict | 현재 리소스 상태·비즈니스 규칙과 충돌 |
| 413 Payload Too Large | 허용 크기를 초과한 업로드 |
| 422 Unprocessable Entity | 문법은 유효하지만 의미 검증에 실패한 입력 |
| 500 Internal Server Error | 서버 애플리케이션 내부 예외 또는 처리 실패 |
| 501 Not Implemented | 서버가 요청 메서드나 기능을 지원하지 않음 |
| 502 Bad Gateway | 게이트웨이가 뒤쪽 서비스에서 잘못된 응답을 받음 |
| 503 Service Unavailable | 점검·과부하 등으로 서비스를 일시적으로 사용할 수 없음 |
| 504 Gateway Timeout | 게이트웨이가 뒤쪽 서비스 응답을 기다리다 시간 초과 |
| 505 HTTP Version Not Supported | 서버가 요청의 HTTP 버전을 지원하지 않음 |
| 506 Variant Also Negotiates | 서버의 콘텐츠 협상 설정에 순환 오류가 있음 |
| 507 Insufficient Storage | 서버 저장 공간이 부족함 |
| 508 Loop Detected | 서버가 요청 처리 중 무한 순환을 감지함 |
| 510 Not Extended | 요청 처리를 위해 추가 확장이 필요함 |
| 511 Network Authentication Required | 네트워크 접근에 추가 인증이 필요함 |

## 공통 판정 함수

`part1_api_automation.utils.response`의 함수를 모든 기능 테스트에서 사용한다.

```python
from part1_api_automation.utils.response import (
    assert_api_success,
    assert_forbidden,
    assert_unauthorized,
)

assert_api_success(response, expected_api_status_code=200)
assert_unauthorized(response)  # HTTP 401만 허용
assert_forbidden(response)     # HTTP 403만 허용
```

LXP API는 HTTP 200을 반환하면서 본문의 `_result.status`를 `fail`로 표시하기도 한다.
이때 HTTP 상태와 내부 상태를 서로 다른 값으로 판정한다.

```python
from part1_api_automation.utils.response import assert_error_response, logic_error

assert_error_response(
    response,
    logic_error(409, error_code="insufficient_permission"),
)
```

위 예시는 다음 세 조건이 모두 정확히 일치해야 통과한다.

1. HTTP 상태 코드가 200이다.
2. `_result.status`가 `fail`이고 `_result.status_code`가 409이다.
3. `fail_code`가 `insufficient_permission`이다.

`status_code in (401, 403)`, `status_code >= 400`, `400 <= status_code < 500`처럼
원인을 구분하지 못하는 판정은 사용하지 않는다. 실제 서버 계약이 불명확하면 여러
값을 허용하지 말고 응답을 먼저 확인한 뒤 TC 기대 결과와 정확한 코드 하나를 확정한다.

## 5xx 처리

일반 기능·입력·권한 TC에서는 5xx를 기대 결과로 사용하지 않는다. 예를 들어 잘못된
입력 TC의 기대값이 400인데 실제로 500이 오면 서버의 예외 처리 결함 후보로 판정한다.

`api_client`는 표준 5xx를 각각 분류하고, 정의되지 않은 5xx는
`other_server_error`로 기록한 `AbortTestError`를 발생시킨 뒤 이후 요청을 차단한다.
502·503·504가 일시적 장애일 가능성이 있어도 자동 재시도하지 않는다.
반복 요청으로 장애 중인 서버에 부하를 더하지 않기 위한 정책이다.

네트워크를 사용하지 않는 모의 응답 테스트처럼 5xx 응답 자체를 직접 검사해야 할
때만 상태별 공통 함수를 사용한다.

```python
from part1_api_automation.utils.response import (
    assert_bad_gateway,
    assert_gateway_timeout,
    assert_internal_server_error,
    assert_service_unavailable,
)

assert_internal_server_error(response)  # 정확히 500
assert_bad_gateway(response)            # 정확히 502
assert_service_unavailable(response)    # 정확히 503
assert_gateway_timeout(response)        # 정확히 504
```

## 신규 상태 추가

반복 사용하는 상태는 `ErrorExpectation` 상수와 편의 함수를 공통 모듈에 추가한다.
API 고유 오류 코드까지 필요한 경우에는 테스트에서 아래와 같이 명시한다.

```python
from part1_api_automation.utils.response import ErrorExpectation, assert_error_response

assert_error_response(
    response,
    ErrorExpectation(http_status=403, error_code="course_access_denied"),
)
```
