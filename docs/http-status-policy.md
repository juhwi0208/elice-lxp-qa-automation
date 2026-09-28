# API 상태 코드 판정 기준

API 자동화에서 오류 상태를 넓은 범위로 허용하면 실제 실패 원인을
구분하기 어렵습니다. 따라서 각 TC는 **HTTP 상태, API 내부 상태, 필요 시
`fail_code`까지 구체적으로 지정**하고 실제 응답이 기대값과 다르면 실패로
판정합니다.

## 1. 기본 원칙

-   `status_code in (401, 403)`처럼 여러 원인을 한 번에 허용하지
    않습니다.
-   `status_code >= 400`, `400 <= status_code < 500` 같은 포괄 판정을
    사용하지 않습니다.
-   서버 계약이 불명확한 경우 임의로 여러 상태를 허용하지 않고 실제
    응답과 명세를 확인해 TC 기대값을 확정합니다.
-   일반 기능·입력·권한 TC에서 HTTP 5xx는 정상적인 Negative 결과로
    취급하지 않습니다.
-   LXP API가 HTTP 200과 본문 내부 실패 상태를 함께 반환하는 경우 HTTP
    상태와 API 내부 상태를 별도로 판정합니다.

## 2. HTTP 상태 사용 기준

  -----------------------------------------------------------------------
  상태                                사용 기준
  ----------------------------------- -----------------------------------
  400 Bad Request                     필수값 누락, 형식·타입·길이 오류 등
                                      잘못된 요청

  401 Unauthorized                    로그인 정보 없음, 만료·위조된 인증
                                      정보

  403 Forbidden                       인증은 되었지만 역할 또는 리소스
                                      접근 권한 없음

  404 Not Found                       존재하지 않거나 삭제된 리소스

  409 Conflict                        현재 리소스 상태·비즈니스 규칙과
                                      충돌

  413 Payload Too Large               허용 크기를 초과한 업로드

  422 Unprocessable Entity            문법은 유효하지만 의미 검증에
                                      실패한 입력

  500 Internal Server Error           서버 애플리케이션 내부 예외 또는
                                      처리 실패

  501 Not Implemented                 서버가 요청 메서드나 기능을
                                      지원하지 않음

  502 Bad Gateway                     게이트웨이가 뒤쪽 서비스에서 잘못된
                                      응답을 받음

  503 Service Unavailable             점검·과부하 등으로 서비스를
                                      일시적으로 사용할 수 없음

  504 Gateway Timeout                 게이트웨이가 뒤쪽 서비스 응답을
                                      기다리다 시간 초과

  505 HTTP Version Not Supported      서버가 요청의 HTTP 버전을 지원하지
                                      않음

  506 Variant Also Negotiates         서버의 콘텐츠 협상 설정에 순환
                                      오류가 있음

  507 Insufficient Storage            서버 저장 공간이 부족함

  508 Loop Detected                   서버가 요청 처리 중 무한 순환을
                                      감지함

  510 Not Extended                    요청 처리를 위해 추가 확장이 필요함

  511 Network Authentication Required 네트워크 접근에 추가 인증이 필요함
  -----------------------------------------------------------------------

표는 공통 판정 모듈이 다루는 HTTP 오류 의미를 정리한 것입니다. 모든
상태가 실제 제품 TC의 기대 결과로 사용된다는 뜻은 아닙니다.

## 3. 공통 판정 함수

공통 응답 판정은 `api.utils.response`의 함수를 사용합니다.

``` python
from api.utils.response import (
    assert_api_success,
    assert_forbidden,
    assert_unauthorized,
)

assert_api_success(response, expected_api_status_code=200)
assert_unauthorized(response)
assert_forbidden(response)
```

`assert_unauthorized()`는 HTTP 401, `assert_forbidden()`은 HTTP 403처럼
지정된 상태를 정확히 판정합니다.

## 4. HTTP 200 + API 내부 실패 응답

LXP API 일부 응답은 HTTP 200을 반환하면서 본문의 `_result.status`를
`fail`로 표시할 수 있습니다. 이 경우 HTTP 상태와 API 내부 상태를
혼동하지 않습니다.

``` python
from api.utils.response import assert_error_response, logic_error

assert_error_response(
    response,
    logic_error(409, error_code="insufficient_permission"),
)
```

위 예시는 다음 조건을 함께 검증합니다.

1.  HTTP 응답이 해당 API 계약에서 사용하는 외부 상태를 만족한다.
2.  `_result.status`가 `fail`이다.
3.  `_result.status_code`가 기대한 논리 상태 코드와 일치한다.
4.  지정한 경우 `fail_code`가 기대 오류 코드와 일치한다.

따라서 HTTP 200이라는 이유만으로 성공으로 판정하지 않습니다.

## 5. 5xx 처리

일반 기능·입력·권한 TC에서 5xx는 기대 결과로 사용하지 않습니다. 예를
들어 입력 오류 TC가 400 또는 API 내부 입력 오류를 기대하는데 서버가
500을 반환하면 정상 Negative 결과가 아니라 서버 오류 분석 대상으로
봅니다.

`api.utils.api_client`는 5xx 응답을 서버 오류 유형으로 분류하고
`AbortTestError`를 발생시켜 같은 테스트의 후속 API 요청을 차단합니다.
502·503·504처럼 일시적 장애일 가능성이 있는 상태도 자동 재시도하지
않습니다. 장애 상황에서 반복 호출로 서버 부하를 키우지 않기 위한
정책입니다.

네트워크 연결 오류와 HTTP 5xx는 서로 다르게 처리합니다. 네트워크 오류는
설정된 범위에서 제한적으로 재시도할 수 있지만, 서버가 실제 5xx 응답을
반환한 경우에는 재시도하지 않습니다.

네트워크를 사용하지 않는 공통 모듈 테스트처럼 5xx 응답 자체를 검증할
때는 상태별 함수를 사용할 수 있습니다.

``` python
from api.utils.response import (
    assert_bad_gateway,
    assert_gateway_timeout,
    assert_internal_server_error,
    assert_service_unavailable,
)

assert_internal_server_error(response)
assert_bad_gateway(response)
assert_service_unavailable(response)
assert_gateway_timeout(response)
```

## 6. 신규 오류 상태 추가

반복해서 사용하는 오류 조건은 `ErrorExpectation`과 공통 판정 함수로
관리합니다. API 고유 오류 코드까지 필요한 경우 TC에서 명시합니다.

``` python
from api.utils.response import ErrorExpectation, assert_error_response

assert_error_response(
    response,
    ErrorExpectation(http_status=403, error_code="course_access_denied"),
)
```

새 판정 로직을 추가할 때도 여러 오류 상태를 하나의 허용 범위로 묶기보다,
TC가 의도한 실패 원인을 식별할 수 있도록 구체적인 기대값을 유지합니다.
