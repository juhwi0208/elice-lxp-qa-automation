"""
공통 API 응답 검증 유틸리티.

이 모듈은 LXP API 응답을 검증하기 위한 재사용 가능한 헬퍼 함수를 제공한다.
각 API 테스트에서 공통으로 사용하며, API별 비즈니스 로직 검증은
각 테스트 파일에서 수행한다.

지원하는 응답 유형:

1. API 성공
   HTTP 200 + `_result.status == "ok"`

   예시:
       {
           "_result": {
               "reason": null,
               "status": "ok",
               "status_code": 200
           },
           ...
       }

2. API 로직 실패
   HTTP 200 + `_result.status == "fail"`

   `_result.status_code`에는 논리적 오류의 HTTP 상태 코드가
   포함될 수 있다.

   예시:
       {
           "_result": {
               "reason": "logic",
               "status": "fail",
               "status_code": 409
           },
           "fail_code": "insufficient_permission",
           "fail_detail": {},
           "fail_message": "you should be Student or above"
       }

3. HTTP 레벨 오류
   HTTP 4xx/5xx와 함께 아래와 같은 응답 본문을 반환한다.

       {
           "code": "...",
           "message": "...",
           "detail": {}
       }

주의:
    HTTP 상태 코드(response.status_code)와
    `_result.status_code`는 서로 다른 값으로 취급한다.

    예를 들어 다음 응답은 정상적인 API 로직 실패 응답이다.

        HTTP 200
        _result.status == "fail"
        _result.status_code == 409

    이 모듈에서는 API별 비즈니스 로직이나 응답 데이터의
    구체적인 값은 검증하지 않는다.
"""

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, Optional
from part1_api_automation.utils.security import mask_sensitive_data

import requests


JSONDict = Dict[str, Any]


@dataclass(frozen=True)
class ServerErrorClassification:
    """5xx 응답의 장애 유형과 운영상 의미."""

    status_code: int
    code: str
    description: str
    transient: bool


@dataclass(frozen=True)
class ErrorExpectation:
    """HTTP 전송 코드와 LXP 논리 오류 코드를 분리한 정확한 기대값."""

    http_status: int | HTTPStatus
    api_status: int | HTTPStatus | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        http_status = int(self.http_status)
        if http_status < 100 or http_status > 599:
            raise ValueError("HTTP 상태 코드는 100~599 범위여야 합니다.")
        if self.api_status is not None:
            api_status = int(self.api_status)
            if api_status < 400 or api_status > 599:
                raise ValueError("API 논리 오류 상태 코드는 400~599 범위여야 합니다.")
            if http_status != HTTPStatus.OK:
                raise ValueError(
                    "LXP 논리 오류의 HTTP 상태 코드는 200이어야 합니다."
                )
        elif http_status < 400 or http_status > 599:
            raise ValueError(
                "HTTP 오류 기대값은 400~599 범위여야 합니다. "
                "HTTP 200 논리 오류는 logic_error()를 사용하세요."
            )


BAD_REQUEST = ErrorExpectation(HTTPStatus.BAD_REQUEST)
UNAUTHORIZED = ErrorExpectation(HTTPStatus.UNAUTHORIZED)
FORBIDDEN = ErrorExpectation(HTTPStatus.FORBIDDEN)
NOT_FOUND = ErrorExpectation(HTTPStatus.NOT_FOUND)
CONFLICT = ErrorExpectation(HTTPStatus.CONFLICT)
PAYLOAD_TOO_LARGE = ErrorExpectation(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
UNPROCESSABLE_ENTITY = ErrorExpectation(HTTPStatus.UNPROCESSABLE_ENTITY)
INTERNAL_SERVER_ERROR = ErrorExpectation(HTTPStatus.INTERNAL_SERVER_ERROR)
NOT_IMPLEMENTED = ErrorExpectation(HTTPStatus.NOT_IMPLEMENTED)
BAD_GATEWAY = ErrorExpectation(HTTPStatus.BAD_GATEWAY)
SERVICE_UNAVAILABLE = ErrorExpectation(HTTPStatus.SERVICE_UNAVAILABLE)
GATEWAY_TIMEOUT = ErrorExpectation(HTTPStatus.GATEWAY_TIMEOUT)
HTTP_VERSION_NOT_SUPPORTED = ErrorExpectation(HTTPStatus.HTTP_VERSION_NOT_SUPPORTED)
VARIANT_ALSO_NEGOTIATES = ErrorExpectation(HTTPStatus.VARIANT_ALSO_NEGOTIATES)
INSUFFICIENT_STORAGE = ErrorExpectation(HTTPStatus.INSUFFICIENT_STORAGE)
LOOP_DETECTED = ErrorExpectation(HTTPStatus.LOOP_DETECTED)
NOT_EXTENDED = ErrorExpectation(HTTPStatus.NOT_EXTENDED)
NETWORK_AUTHENTICATION_REQUIRED = ErrorExpectation(
    HTTPStatus.NETWORK_AUTHENTICATION_REQUIRED
)


_SERVER_ERROR_CLASSIFICATIONS = {
    500: ServerErrorClassification(
        500,
        "internal_server_error",
        "서버 애플리케이션 내부 예외 또는 처리 실패",
        False,
    ),
    501: ServerErrorClassification(
        501,
        "not_implemented",
        "서버가 요청 메서드나 기능을 지원하지 않음",
        False,
    ),
    502: ServerErrorClassification(
        502,
        "bad_gateway",
        "게이트웨이가 뒤쪽 서비스에서 유효한 응답을 받지 못함",
        True,
    ),
    503: ServerErrorClassification(
        503,
        "service_unavailable",
        "점검·과부하 등으로 서비스를 일시적으로 사용할 수 없음",
        True,
    ),
    504: ServerErrorClassification(
        504,
        "gateway_timeout",
        "게이트웨이가 뒤쪽 서비스의 응답을 제한 시간 안에 받지 못함",
        True,
    ),
    505: ServerErrorClassification(
        505,
        "http_version_not_supported",
        "서버가 요청에 사용된 HTTP 버전을 지원하지 않음",
        False,
    ),
    506: ServerErrorClassification(
        506,
        "variant_also_negotiates",
        "서버의 콘텐츠 협상 설정에 순환 오류가 있음",
        False,
    ),
    507: ServerErrorClassification(
        507,
        "insufficient_storage",
        "서버가 요청 처리를 완료할 저장 공간이 부족함",
        False,
    ),
    508: ServerErrorClassification(
        508,
        "loop_detected",
        "서버가 요청 처리 중 무한 순환을 감지함",
        False,
    ),
    510: ServerErrorClassification(
        510,
        "not_extended",
        "요청 처리를 위해 추가 확장이 필요함",
        False,
    ),
    511: ServerErrorClassification(
        511,
        "network_authentication_required",
        "네트워크 접근을 위한 추가 인증이 필요함",
        False,
    ),
}


def classify_server_error(status_code: int | HTTPStatus) -> ServerErrorClassification:
    """5xx 상태를 개별 장애 유형으로 분류한다.

    `transient`는 장애가 일시적일 가능성을 나타낼 뿐 자동 재시도를 허용하지 않는다.
    이 프로젝트는 어떤 5xx든 최초 1회 수신 즉시 후속 API 요청을 중단한다.
    """
    status = int(status_code)
    if status < 500 or status > 599:
        raise ValueError("서버 오류 분류에는 500~599 상태 코드만 사용할 수 있습니다.")
    return _SERVER_ERROR_CLASSIFICATIONS.get(
        status,
        ServerErrorClassification(
            status,
            "other_server_error",
            "기타 서버 오류",
            False,
        ),
    )


def logic_error(
    api_status: int | HTTPStatus,
    *,
    error_code: str | None = None,
) -> ErrorExpectation:
    """HTTP 200 + `_result.status=fail` 형식의 정확한 기대값을 만든다."""
    return ErrorExpectation(
        http_status=HTTPStatus.OK,
        api_status=api_status,
        error_code=error_code,
    )


def get_response_json(response: requests.Response) -> JSONDict:
    """
    응답 본문을 JSON 딕셔너리로 파싱하여 반환한다.

    Args:
        response: requests.Response 객체.

    Returns:
        파싱된 JSON 응답 본문.

    Raises:
        AssertionError:
            응답 본문이 유효한 JSON이 아니거나
            JSON 본문이 딕셔너리가 아닌 경우.
    """
    try:
        body = response.json()
    except ValueError as exc:
        raise AssertionError(
            "응답 본문이 유효한 JSON이 아닙니다.\n"
            f"HTTP 상태 코드: {response.status_code}\n"
            f"응답 본문: {mask_sensitive_data(response.text)}"
        )
    assert isinstance(body, dict), (
        "응답 JSON 본문이 딕셔너리여야 합니다.\n"
        f"실제 타입: {type(body).__name__}\n"
        f"응답 본문: {mask_sensitive_data(body)}"
    )

    return body


def assert_http_status(
    response: requests.Response,
    expected_status_code: int | HTTPStatus,
) -> requests.Response:
    """
    응답의 HTTP 상태 코드를 검증한다.

    이 함수는 HTTP 레이어만 검증하며,
    `_result`, `fail_code` 등의 API 응답 필드는 검사하지 않는다.

    Args:
        response: requests.Response 객체.
        expected_status_code: 기대하는 HTTP 상태 코드.

    Returns:
        검증된 원본 response 객체.

    Raises:
        AssertionError:
            실제 HTTP 상태 코드가 기대값과 다른 경우.
    """
    expected = int(expected_status_code)
    assert response.status_code == expected, (
        "예상과 다른 HTTP 상태 코드입니다.\n"
        f"기대 값: {expected}\n"
        f"실제 값: {response.status_code}\n"
        f"응답 본문: {mask_sensitive_data(response.text)}"
    )

    return response


def assert_api_success(
    response: requests.Response,
    expected_status_code: int | HTTPStatus = HTTPStatus.OK,
    expected_api_status_code: int | HTTPStatus | None = None,
) -> JSONDict:
    """
    LXP API 성공 응답을 검증한다.

    성공 응답의 기대 형태:

        HTTP 상태 코드 == expected_status_code
        _result.status == "ok"

    `_result.status_code`는 API 응답마다 존재 여부가 다를 수 있으므로
    공통 필수 검증 항목으로 사용하지 않는다.

    Args:
        response: requests.Response 객체.
        expected_status_code: 기대하는 HTTP 상태 코드. 기본값은 200.

    Returns:
        파싱된 JSON 응답 본문.

    Raises:
        AssertionError:
            HTTP 상태 코드가 기대값과 다르거나,
            `_result`가 없거나,
            `_result.status`가 `"ok"`가 아닌 경우.
    """
    assert_http_status(response, expected_status_code)

    body = get_response_json(response)

    result = body.get("_result")

    assert isinstance(result, dict), (
        f"응답에 유효한 `_result` 객체가 없습니다.\n응답 본문: {mask_sensitive_data(body)}"
    )

    assert result.get("status") == "ok", (
        "API 응답이 성공 응답이 아닙니다.\n"
        "기대하는 `_result.status`: 'ok'\n"
        f"실제 `_result.status`: {result.get('status')}\n"
        f"응답 본문: {mask_sensitive_data(body)}"
    )

    if expected_api_status_code is not None:
        expected_api_status = int(expected_api_status_code)
        assert result.get("status_code") == expected_api_status, (
            "예상과 다른 API 성공 상태 코드입니다.\n"
            f"기대하는 `_result.status_code`: {expected_api_status}\n"
            f"실제 `_result.status_code`: {result.get('status_code')}\n"
            f"응답 본문: {mask_sensitive_data(body)}"
        )

    return body


def assert_error_response(
    response: requests.Response,
    expected: ErrorExpectation,
) -> JSONDict:
    """하나의 명시적 오류 계약만 허용해 상태 코드를 구체적으로 판정한다.

    `expected.api_status`가 있으면 HTTP 200 논리 실패 형식을 검증하고,
    없으면 HTTP 레이어 오류를 검증한다. 여러 상태 코드의 묶음이나 범위는
    받지 않으므로 각 TC가 401/403/404 등을 명확하게 선택해야 한다.
    """
    expected_http = int(expected.http_status)
    assert_http_status(response, expected_http)
    body = get_response_json(response)

    if expected.api_status is not None:
        result = body.get("_result")
        assert isinstance(result, dict), (
            "논리 오류 응답에 `_result` 객체가 없습니다.\n"
            f"응답 본문: {mask_sensitive_data(body)}"
        )
        assert result.get("status") == "fail", (
            "논리 오류 응답의 `_result.status`는 'fail'이어야 합니다.\n"
            f"실제 값: {result.get('status')}\n응답 본문: {mask_sensitive_data(body)}"
        )
        expected_api_status = int(expected.api_status)
        assert result.get("status_code") == expected_api_status, (
            "예상과 다른 API 논리 오류 상태 코드입니다.\n"
            f"기대 값: {expected_api_status}\n"
            f"실제 값: {result.get('status_code')}\n응답 본문: {mask_sensitive_data(body)}"
        )
        actual_error_code = body.get("fail_code")
    else:
        result = body.get("_result")
        assert not (isinstance(result, dict) and result.get("status") == "ok"), (
            "HTTP 오류 응답이 성공으로 표시됐습니다.\n"
            f"응답 본문: {mask_sensitive_data(body)}"
        )
        actual_error_code = body.get("code", body.get("fail_code"))

    if expected.error_code is not None:
        assert actual_error_code == expected.error_code, (
            "예상과 다른 오류 코드입니다.\n"
            f"기대 값: {expected.error_code}\n"
            f"실제 값: {actual_error_code}\n응답 본문: {mask_sensitive_data(body)}"
        )

    return body


def assert_bad_request(response: requests.Response) -> JSONDict:
    return assert_error_response(response, BAD_REQUEST)


def assert_unauthorized(response: requests.Response) -> JSONDict:
    return assert_error_response(response, UNAUTHORIZED)


def assert_forbidden(response: requests.Response) -> JSONDict:
    return assert_error_response(response, FORBIDDEN)


def assert_not_found(response: requests.Response) -> JSONDict:
    return assert_error_response(response, NOT_FOUND)


def assert_conflict(response: requests.Response) -> JSONDict:
    return assert_error_response(response, CONFLICT)


def assert_payload_too_large(response: requests.Response) -> JSONDict:
    return assert_error_response(response, PAYLOAD_TOO_LARGE)


def assert_unprocessable_entity(response: requests.Response) -> JSONDict:
    return assert_error_response(response, UNPROCESSABLE_ENTITY)


def assert_internal_server_error(response: requests.Response) -> JSONDict:
    return assert_error_response(response, INTERNAL_SERVER_ERROR)


def assert_not_implemented(response: requests.Response) -> JSONDict:
    return assert_error_response(response, NOT_IMPLEMENTED)


def assert_bad_gateway(response: requests.Response) -> JSONDict:
    return assert_error_response(response, BAD_GATEWAY)


def assert_service_unavailable(response: requests.Response) -> JSONDict:
    return assert_error_response(response, SERVICE_UNAVAILABLE)


def assert_gateway_timeout(response: requests.Response) -> JSONDict:
    return assert_error_response(response, GATEWAY_TIMEOUT)


def assert_http_version_not_supported(response: requests.Response) -> JSONDict:
    return assert_error_response(response, HTTP_VERSION_NOT_SUPPORTED)


def assert_variant_also_negotiates(response: requests.Response) -> JSONDict:
    return assert_error_response(response, VARIANT_ALSO_NEGOTIATES)


def assert_insufficient_storage(response: requests.Response) -> JSONDict:
    return assert_error_response(response, INSUFFICIENT_STORAGE)


def assert_loop_detected(response: requests.Response) -> JSONDict:
    return assert_error_response(response, LOOP_DETECTED)


def assert_not_extended(response: requests.Response) -> JSONDict:
    return assert_error_response(response, NOT_EXTENDED)


def assert_network_authentication_required(response: requests.Response) -> JSONDict:
    return assert_error_response(response, NETWORK_AUTHENTICATION_REQUIRED)


def assert_api_failure(
    response: requests.Response,
    expected_status_code: Optional[int] = 200,
    expected_api_status_code: Optional[int] = None,
    fail_code: Optional[str] = None,
) -> JSONDict:
    """
    LXP API 로직 실패 응답을 검증한다.

    API 로직 실패는 HTTP 200으로 응답하면서
    `_result.status == "fail"`을 반환할 수 있다.

    예시:

        HTTP 200

        {
            "_result": {
                "reason": "logic",
                "status": "fail",
                "status_code": 409
            },
            "fail_code": "insufficient_permission",
            "fail_detail": {},
            "fail_message": "..."
        }

    HTTP 상태 코드와 `_result.status_code`는 서로 다른 값으로 취급한다.

    Args:
        response:
            requests.Response 객체.

        expected_status_code:
            기대하는 HTTP 상태 코드. 기본값은 200이며 None은 허용하지 않는다.

        expected_api_status_code:
            기대하는 `_result.status_code`. 반드시 지정해야 한다.

        fail_code:
            기대하는 `fail_code`.
            None이면 검증하지 않는다.

    Returns:
        파싱된 JSON 응답 본문.

    Raises:
        AssertionError:
            기대한 API 로직 실패 응답 형태와 다른 경우.
    """
    if expected_status_code is None or expected_api_status_code is None:
        raise ValueError(
            "오류 상태를 구체적으로 판정하려면 expected_status_code와 "
            "expected_api_status_code를 모두 지정해야 합니다."
        )

    assert_http_status(response, expected_status_code)

    body = get_response_json(response)

    result = body.get("_result")

    assert isinstance(result, dict), (
        f"응답에 유효한 `_result` 객체가 없습니다.\n응답 본문: {mask_sensitive_data(body)}"
    )

    assert result.get("status") == "fail", (
        "API 응답이 실패 응답이 아닙니다.\n"
        "기대하는 `_result.status`: 'fail'\n"
        f"실제 `_result.status`: {result.get('status')}\n"
        f"응답 본문: {mask_sensitive_data(body)}"
    )

    actual_api_status_code = result.get("status_code")

    assert actual_api_status_code == expected_api_status_code, (
        "예상과 다른 API 상태 코드입니다.\n"
        f"기대하는 `_result.status_code`: {expected_api_status_code}\n"
        f"실제 `_result.status_code`: {actual_api_status_code}\n"
        f"응답 본문: {mask_sensitive_data(body)}"
    )

    if fail_code is not None:
        actual_fail_code = body.get("fail_code")

        assert actual_fail_code == fail_code, (
            "예상과 다른 API 실패 코드입니다.\n"
            f"기대하는 `fail_code`: {fail_code}\n"
            f"실제 `fail_code`: {actual_fail_code}\n"
            f"응답 본문: {mask_sensitive_data(body)}"
        )

    return body


def assert_http_error(
    response: requests.Response,
    expected_status_code: Optional[int] = None,
    code: Optional[str] = None,
) -> JSONDict:
    """
    HTTP 레벨 오류 응답을 검증한다.

    HTTP 4xx/5xx 응답에서 `_result`가 존재하지 않고
    다음과 같은 공통 오류 응답 형태를 사용하는 경우에 사용한다.

        {
            "code": "...",
            "message": "...",
            "detail": {}
        }

    `code`의 실제 값은 API마다 다를 수 있으므로
    기본적으로 필드 존재 여부만 검증한다.

    Args:
        response:
            requests.Response 객체.

        expected_status_code:
            기대하는 HTTP 오류 상태 코드. 반드시 지정해야 한다.

        code:
            기대하는 `code` 값.
            None이면 값 자체는 검증하지 않는다.

    Returns:
        파싱된 JSON 응답 본문.

    Raises:
        AssertionError:
            HTTP 상태 코드가 다르거나,
            `code`, `message`, `detail` 필드가 없는 경우.
    """
    if expected_status_code is None:
        raise ValueError(
            "오류 상태를 구체적으로 판정하려면 expected_status_code를 지정해야 합니다."
        )

    assert_http_status(response, expected_status_code)

    body = get_response_json(response)

    assert "code" in body, (
        f"HTTP 오류 응답에 `code` 필드가 없습니다.\n응답 본문: {mask_sensitive_data(body)}"
    )

    assert "message" in body, (
        f"HTTP 오류 응답에 `message` 필드가 없습니다.\n응답 본문: {mask_sensitive_data(body)}"
    )

    assert "detail" in body, (
        f"HTTP 오류 응답에 `detail` 필드가 없습니다.\n응답 본문: {mask_sensitive_data(body)}"
    )

    if code is not None:
        actual_code = body.get("code")

        assert actual_code == code, (
            "예상과 다른 HTTP 오류 코드입니다.\n"
            f"기대하는 `code`: {code}\n"
            f"실제 `code`: {actual_code}\n"
            f"응답 본문: {mask_sensitive_data(body)}"
        )

    return body
