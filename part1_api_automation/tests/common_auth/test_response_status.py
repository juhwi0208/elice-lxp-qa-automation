"""공통 API 상태 코드 판정 유틸리티의 단위 테스트."""

from __future__ import annotations

import pytest

from part1_api_automation.utils.response import (
    ErrorExpectation,
    assert_api_failure,
    assert_api_success,
    assert_error_response,
    assert_http_error,
    assert_internal_server_error,
    assert_unauthorized,
    classify_server_error,
    logic_error,
)


class FakeResponse:
    """네트워크 호출 없이 requests.Response의 필요한 부분만 흉내 낸다."""

    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body
        self.text = repr(body)

    def json(self) -> dict:
        return self._body


def test_api_success_checks_http_and_internal_status_codes() -> None:
    response = FakeResponse(
        200,
        {"_result": {"status": "ok", "status_code": 200, "reason": None}},
    )

    body = assert_api_success(response, expected_api_status_code=200)

    assert body["_result"]["status"] == "ok"


def test_api_success_rejects_wrong_internal_status_code() -> None:
    response = FakeResponse(
        200,
        {"_result": {"status": "ok", "status_code": 201, "reason": None}},
    )

    with pytest.raises(AssertionError, match="status_code"):
        assert_api_success(response, expected_api_status_code=200)


def test_http_error_requires_one_exact_status_code() -> None:
    response = FakeResponse(
        401,
        {"code": "unauthorized", "message": "login required", "detail": {}},
    )

    assert_unauthorized(response)

    response.status_code = 403
    with pytest.raises(AssertionError, match="HTTP"):
        assert_unauthorized(response)


def test_logical_error_checks_internal_status_and_fail_code() -> None:
    response = FakeResponse(
        200,
        {
            "_result": {"status": "fail", "status_code": 409, "reason": "logic"},
            "fail_code": "insufficient_permission",
        },
    )

    body = assert_error_response(
        response,
        logic_error(409, error_code="insufficient_permission"),
    )

    assert body["fail_code"] == "insufficient_permission"


def test_logical_error_rejects_different_internal_status_code() -> None:
    response = FakeResponse(
        200,
        {
            "_result": {"status": "fail", "status_code": 403, "reason": "logic"},
            "fail_code": "insufficient_permission",
        },
    )

    with pytest.raises(AssertionError, match="API"):
        assert_error_response(response, logic_error(409))


@pytest.mark.parametrize("status_code", [99, 600])
def test_error_expectation_rejects_invalid_http_status(status_code: int) -> None:
    with pytest.raises(ValueError, match="100~599"):
        ErrorExpectation(status_code)


@pytest.mark.parametrize("status_code", [399, 600])
def test_error_expectation_rejects_invalid_api_error_status(status_code: int) -> None:
    with pytest.raises(ValueError, match="400~599"):
        ErrorExpectation(200, api_status=status_code)


def test_error_expectation_rejects_success_status_without_logical_error() -> None:
    with pytest.raises(ValueError, match="HTTP 오류"):
        ErrorExpectation(200)


def test_logical_error_requires_http_200() -> None:
    with pytest.raises(ValueError, match="200"):
        ErrorExpectation(403, api_status=409)


def test_legacy_failure_helper_requires_internal_status_code() -> None:
    response = FakeResponse(
        200,
        {"_result": {"status": "fail", "status_code": 409}},
    )

    with pytest.raises(ValueError, match="expected_api_status_code"):
        assert_api_failure(response)


def test_legacy_http_error_helper_requires_http_status_code() -> None:
    response = FakeResponse(
        401,
        {"code": "unauthorized", "message": "login required", "detail": {}},
    )

    with pytest.raises(ValueError, match="expected_status_code"):
        assert_http_error(response)


@pytest.mark.parametrize(
    ("status_code", "error_code", "transient"),
    [
        (500, "internal_server_error", False),
        (501, "not_implemented", False),
        (502, "bad_gateway", True),
        (503, "service_unavailable", True),
        (504, "gateway_timeout", True),
        (505, "http_version_not_supported", False),
        (506, "variant_also_negotiates", False),
        (507, "insufficient_storage", False),
        (508, "loop_detected", False),
        (510, "not_extended", False),
        (511, "network_authentication_required", False),
        (509, "other_server_error", False),
    ],
)
def test_server_errors_are_classified_individually(
    status_code: int,
    error_code: str,
    transient: bool,
) -> None:
    classification = classify_server_error(status_code)

    assert classification.status_code == status_code
    assert classification.code == error_code
    assert classification.transient is transient


def test_server_error_classifier_rejects_non_5xx_status() -> None:
    with pytest.raises(ValueError, match="500~599"):
        classify_server_error(404)


def test_internal_server_error_requires_exactly_500() -> None:
    response = FakeResponse(500, {"detail": "Internal Server Error"})
    assert_internal_server_error(response)

    response.status_code = 503
    with pytest.raises(AssertionError, match="HTTP"):
        assert_internal_server_error(response)
