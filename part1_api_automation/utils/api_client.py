"""
api_client.py
공통 HTTP 요청 클라이언트.

Safety Design 준수:
- 모든 요청에 타임아웃(TIMEOUT) 적용
- 연속 호출 간 최소 대기(CALL_INTERVAL) 적용
- 5xx 서버 에러 발생 즉시 AbortTestError 발생 (반복 호출 금지)
- 네트워크 에러는 최대 1회까지만 재시도
"""

import os
import threading
import time
from urllib.parse import urlparse

import requests

from part1_api_automation.utils.config import (
    Config,
    configured_api_base_urls,
    require_service_base_url,
)
from part1_api_automation.utils.response import classify_server_error


class AbortTestError(RuntimeError):
    """5xx 수신 후 테스트 실행과 추가 API 호출을 중단할 때 발생한다."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class RequestLimitExceeded(RuntimeError):
    """테스트 실행 전체의 HTTP 요청 상한을 초과했을 때 발생한다."""


class UnsafeRequestError(RuntimeError):
    """승인되지 않은 대상 또는 상태 변경 요청을 차단할 때 발생한다."""


_state_lock = threading.Lock()
_request_count = 0
_abort_reason: str | None = None


def reset_safety_state() -> None:
    """오프라인 단위 테스트를 위해 프로세스 공용 안전 상태를 초기화한다."""
    global _request_count, _abort_reason
    with _state_lock:
        _request_count = 0
        _abort_reason = None


def request_count() -> int:
    """현재 프로세스에서 수행한 실제 HTTP 호출 수를 반환한다."""
    with _state_lock:
        return _request_count


def _reserve_request() -> None:
    """중단 상태와 전체 요청 상한을 확인한 뒤 호출 1회를 예약한다."""
    global _request_count
    with _state_lock:
        if _abort_reason is not None:
            raise AbortTestError(
                "이전 5xx 응답으로 API 호출이 중단된 상태입니다. "
                f"최초 원인: {_abort_reason}"
            )
        if _request_count >= Config.MAX_REQUESTS:
            raise RequestLimitExceeded(
                f"테스트 실행 전체 요청 상한({Config.MAX_REQUESTS}회)에 도달했습니다."
            )
        _request_count += 1


def _latch_abort(reason: str) -> None:
    global _abort_reason
    with _state_lock:
        if _abort_reason is None:
            _abort_reason = reason


def _validate_target_url(url: str) -> None:
    """토큰이 명시적으로 승인된 QA API 호스트 밖으로 전송되는 것을 막는다."""
    parsed_target = urlparse(url)

    if parsed_target.scheme != "https" or not parsed_target.hostname:
        raise UnsafeRequestError("요청 URL은 완전한 HTTPS 주소여야 합니다.")
    if parsed_target.username or parsed_target.password:
        raise UnsafeRequestError("요청 URL에는 사용자 정보를 포함할 수 없습니다.")
    if parsed_target.query or parsed_target.fragment:
        raise UnsafeRequestError(
            "요청 URL에 쿼리나 프래그먼트를 직접 넣지 말고 params 인자를 사용하세요."
        )
    approved_hosts = {
        urlparse(base_url).hostname.lower()
        for base_url in configured_api_base_urls()
    }
    if parsed_target.hostname.lower() not in approved_hosts:
        raise UnsafeRequestError("요청 대상이 승인된 QA API 호스트와 다릅니다.")
    if parsed_target.port not in (None, 443):
        raise UnsafeRequestError("요청 URL은 기본 HTTPS 포트만 사용할 수 있습니다.")


def _mutation_is_enabled(confirmed: bool) -> bool:
    env_enabled = os.getenv("LXP_ALLOW_MUTATING_REQUESTS", "").strip().lower()
    return confirmed and env_enabled == "true"


def _validate_password_login(url: str, payload: dict | None) -> None:
    """비밀번호 로그인 예외를 승인된 Account API의 단일 경로로 제한한다."""
    expected_url = f"{require_service_base_url('account')}/login/pw"
    if url.rstrip("/") != expected_url:
        raise UnsafeRequestError(
            "인증 요청은 승인된 Account API의 /login/pw 경로만 사용할 수 있습니다."
        )
    if not isinstance(payload, dict) or set(payload) != {"login_id", "password"}:
        raise UnsafeRequestError("로그인 요청 필드가 허용된 형식과 다릅니다.")
    if not all(isinstance(payload[key], str) and payload[key] for key in payload):
        raise UnsafeRequestError("로그인 요청의 인증정보가 비어 있습니다.")


def _request(
    method: str,
    url: str,
    headers: dict,
    *,
    params: dict | None = None,
    json: dict | None = None,
    data: dict | None = None,
    files=None,
    retry: bool = True,
    confirmed: bool = False,
    password_login: bool = False,
    state_changing: bool = False,
) -> requests.Response:
    """
    내부 공통 요청 메서드.

    - 타임아웃: Config.TIMEOUT
    - 호출 간격: Config.CALL_INTERVAL
    - 5xx: AbortTestError 즉시 발생
    - 네트워크 에러: 최대 1회 재시도
    """
    method_name = method.strip().upper()
    _validate_target_url(url)

    if password_login:
        if method_name != "POST":
            raise UnsafeRequestError("비밀번호 로그인은 POST 요청만 허용됩니다.")
        _validate_password_login(url, json)
    elif (
        state_changing or method_name in {"POST", "PUT", "PATCH", "DELETE"}
    ) and not _mutation_is_enabled(confirmed):
        raise UnsafeRequestError(
            "상태 변경 요청이 차단되었습니다. 승인 후 "
            "LXP_ALLOW_MUTATING_REQUESTS=true와 confirmed=True를 함께 지정하세요."
        )

    attempts = 2 if retry else 1
    for attempt in range(attempts):
        time.sleep(Config.CALL_INTERVAL)
        _reserve_request()

        try:
            resp = requests.request(
                method_name,
                url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=Config.TIMEOUT,
                allow_redirects=False,
            )
            break
        except requests.exceptions.RequestException:
            if attempt + 1 == attempts:
                raise

    if resp.status_code >= 500:
        classification = classify_server_error(resp.status_code)
        reason = (
            f"{method_name} {url} -> {classification.status_code} "
            f"({classification.code})"
        )
        _latch_abort(reason)

        raise AbortTestError(
            f"[ABORT] 서버 에러 발생 — 추가 호출을 중단합니다.\n"
            f"  URL   : {method_name} {url}\n"
            f"  Status: {classification.status_code}\n"
            f"  Type  : {classification.code}\n"
            f"  Cause : {classification.description}",
            status_code=classification.status_code,
            error_code=classification.code,
        )

    return resp


def post_password_login(
    url: str,
    *,
    login_id: str,
    password: str,
) -> requests.Response:
    """
    승인된 Account API의 비밀번호 로그인을 수행한다.

    인증정보는 요청 본문으로만 전달하며 오류 메시지나 로그에 포함하지 않는다.
    일반 상태 변경 POST와 달리 별도 실행 승인값은 요구하지 않지만, 대상 URL과
    요청 필드는 이 함수 내부에서 엄격히 제한한다.
    """
    return _request(
        "POST",
        url,
        {},
        json={"login_id": login_id, "password": password},
        retry=False,
        password_login=True,
    )


def get(
    url: str,
    headers: dict,
    params: dict | None = None,
) -> requests.Response:
    """
    GET 요청을 보낸다.

    Args:
        url: 전체 요청 URL
        headers: 인증 헤더 포함 딕셔너리
        params: 쿼리 파라미터 (선택)

    Returns:
        requests.Response
    """
    return _request(
        "GET",
        url,
        headers,
        params=params,
    )


def get_state_changing(
    url: str,
    headers: dict,
    params: dict | None = None,
    *,
    confirmed: bool = False,
) -> requests.Response:
    """GET 형식이지만 서버 상태를 바꾸는 레거시 API를 안전하게 호출한다.

    일반 GET과 달리 ``LXP_ALLOW_MUTATING_REQUESTS=true`` 및
    ``confirmed=True``가 모두 필요하다. 중복 변경 위험을 막기 위해 네트워크
    오류가 발생해도 자동 재시도하지 않는다.
    """
    return _request(
        "GET",
        url,
        headers,
        params=params,
        retry=False,
        confirmed=confirmed,
        state_changing=True,
    )


def post(
    url: str,
    headers: dict,
    json: dict | None = None,
    *,
    data: dict | None = None,
    files=None,
    confirmed: bool = False,
) -> requests.Response:
    """
    POST 요청을 보낸다.

    Args:
        url: 전체 요청 URL
        headers: 인증 헤더 포함 딕셔너리
        json: JSON 요청 바디 (선택)
        data: form 요청 데이터 (선택)
        files: multipart 파일 데이터 (선택)
        confirmed: 상태 변경 요청 실행 승인 여부

    Returns:
        requests.Response
    """
    return _request(
        "POST",
        url,
        headers,
        json=json,
        data=data,
        files=files,
        confirmed=confirmed,
    )


def patch(
    url: str,
    headers: dict,
    json: dict | None = None,
    *,
    confirmed: bool = False,
) -> requests.Response:
    """
    PATCH 요청을 보낸다.

    Args:
        url: 전체 요청 URL
        headers: 인증 헤더 포함 딕셔너리
        json: 요청 바디 (선택)

    Returns:
        requests.Response
    """
    return _request("PATCH", url, headers, json=json, confirmed=confirmed)


def delete(
    url: str,
    headers: dict,
    params: dict | None = None,
    *,
    json: dict | None = None,
    confirmed: bool = False,
) -> requests.Response:
    """
    DELETE 요청을 보낸다.

    Args:
        url: 전체 요청 URL
        headers: 인증 헤더 포함 딕셔너리
        params: 쿼리 파라미터 (선택)
        json: 요청 바디 (선택, 일부 API는 DELETE 시 body가 필요)

    Returns:
        requests.Response
    """
    return _request("DELETE", url, headers, params=params, json=json, confirmed=confirmed)
