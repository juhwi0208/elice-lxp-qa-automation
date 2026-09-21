"""실서비스를 호출하지 않는 공통 인증·HTTP 안전장치 단위 테스트."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from part1_api_automation.utils import api_client, token_manager
from part1_api_automation.utils.security import mask_sensitive_data
from part1_api_automation.utils.config import (
    Config,
    require_service_base_url,
    validate_base_url,
)
from part1_api_automation.utils.response import assert_http_status


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        text: str = "ok",
        json_body: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self._json_body = json_body or {}

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def json(self) -> dict:
        return self._json_body


@pytest.fixture(autouse=True)
def isolated_safety_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LXP_API_BASE_URL", "https://dev-qatrack-api.dev.elicer.io")
    monkeypatch.setattr(Config, "CALL_INTERVAL", 0)
    monkeypatch.setattr(Config, "MAX_REQUESTS", 100)
    api_client.reset_safety_state()
    yield
    api_client.reset_safety_state()


def test_base_url_is_limited_to_fixed_qa_domain() -> None:
    assert (
        validate_base_url("https://dev-qatrack-api.dev.elicer.io/")
        == "https://dev-qatrack-api.dev.elicer.io"
    )

    with pytest.raises(EnvironmentError):
        validate_base_url("https://example.com")


def test_auth_header_repr_redacts_token_without_changing_request_value() -> None:
    headers = token_manager.RedactedAuthHeaders(
        {"Authorization": "Bearer actual-secret", "Accept": "application/json"}
    )

    assert headers["Authorization"] == "Bearer actual-secret"
    assert "actual-secret" not in repr(headers)
    assert "<redacted>" in repr(headers)


def test_presigned_url_signature_is_redacted_from_failure_output() -> None:
    masked = mask_sensitive_data(
        {"logo_url": "https://files.example.test/image.png?se=tomorrow&sig=secret"}
    )

    assert masked["logo_url"].endswith("se=tomorrow&sig=***")
    assert "secret" not in masked["logo_url"]


def test_request_rejects_another_host_before_sending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_request(*args: Any, **kwargs: Any) -> FakeResponse:
        nonlocal called
        called = True
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)

    with pytest.raises(api_client.UnsafeRequestError):
        api_client.get("https://example.com/collect-token", {"Authorization": "secret"})

    assert called is False


def test_request_accepts_configured_classroom_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://dev-qatrack-classroom-api.dev.elicer.io/classroom/example/course"
    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: FakeResponse())

    response = api_client.get(url, {})

    assert_http_status(response, 200)


def test_unknown_api_service_is_rejected() -> None:
    with pytest.raises(EnvironmentError, match="지원하지 않는 API 서비스"):
        require_service_base_url("unknown")


def test_request_rejects_query_embedded_in_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_request(*args: Any, **kwargs: Any) -> FakeResponse:
        nonlocal called
        called = True
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)

    with pytest.raises(api_client.UnsafeRequestError):
        api_client.get(
            "https://dev-qatrack-api.dev.elicer.io/schedule?token=secret", {}
        )

    assert called is False


def test_mutation_requires_environment_and_explicit_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://dev-qatrack-api.dev.elicer.io/schedule"
    monkeypatch.delenv("LXP_ALLOW_MUTATING_REQUESTS", raising=False)
    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(api_client.UnsafeRequestError):
        api_client.post(url, {}, confirmed=True)

    monkeypatch.setenv("LXP_ALLOW_MUTATING_REQUESTS", "true")
    with pytest.raises(api_client.UnsafeRequestError):
        api_client.post(url, {})

    response = api_client.post(url, {}, confirmed=True)
    assert_http_status(response, 200)


def test_state_changing_get_requires_environment_and_explicit_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://dev-qatrack-api.dev.elicer.io/reset"
    monkeypatch.delenv("LXP_ALLOW_MUTATING_REQUESTS", raising=False)
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, target: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": target, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)

    with pytest.raises(api_client.UnsafeRequestError):
        api_client.get_state_changing(url, {}, confirmed=True)

    monkeypatch.setenv("LXP_ALLOW_MUTATING_REQUESTS", "true")
    with pytest.raises(api_client.UnsafeRequestError):
        api_client.get_state_changing(url, {})

    response = api_client.get_state_changing(
        url,
        {},
        params={"material_quiz_id": 1327},
        confirmed=True,
    )

    assert_http_status(response, 200)
    assert len(calls) == 1
    assert calls[0]["method"] == "GET"
    assert calls[0]["params"] == {"material_quiz_id": 1327}


def test_password_login_uses_only_approved_account_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse(json_body={"access_token": "issued-token"})

    monkeypatch.delenv("LXP_ALLOW_MUTATING_REQUESTS", raising=False)
    monkeypatch.setattr(requests, "request", fake_request)

    response = api_client.post_password_login(
        "https://dev-qatrack-account-api.dev.elicer.io/login/pw",
        login_id="learner@example.com",
        password="password-secret",
    )

    assert_http_status(response, 200)
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert calls[0]["json"] == {
        "login_id": "learner@example.com",
        "password": "password-secret",
    }
    assert calls[0]["timeout"] == Config.TIMEOUT
    assert calls[0]["allow_redirects"] is False


def test_password_login_rejects_non_login_path_before_sending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_request(*args: Any, **kwargs: Any) -> FakeResponse:
        nonlocal called
        called = True
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)

    with pytest.raises(api_client.UnsafeRequestError, match="/login/pw"):
        api_client.post_password_login(
            "https://dev-qatrack-account-api.dev.elicer.io/account/delete",
            login_id="learner@example.com",
            password="password-secret",
        )

    assert called is False


def test_token_manager_login_delegates_without_exposing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_login(url: str, *, login_id: str, password: str) -> FakeResponse:
        captured.update(url=url, login_id=login_id, password=password)
        return FakeResponse(json_body={"access_token": "issued-token"})

    monkeypatch.setenv(
        "LXP_ACCOUNT_API_BASE_URL",
        "https://dev-qatrack-account-api.dev.elicer.io",
    )
    monkeypatch.setattr(api_client, "post_password_login", fake_login)

    assert token_manager._login(" learner@example.com ", " password-secret ") == (
        "issued-token"
    )
    assert captured == {
        "url": "https://dev-qatrack-account-api.dev.elicer.io/login/pw",
        "login_id": "learner@example.com",
        "password": "password-secret",
    }

    monkeypatch.setattr(
        api_client,
        "post_password_login",
        lambda *args, **kwargs: FakeResponse(status_code=401),
    )
    with pytest.raises(token_manager.LoginError) as exc_info:
        token_manager._login("learner@example.com", "password-secret")

    error_text = str(exc_info.value)
    assert "learner@example.com" not in error_text
    assert "password-secret" not in error_text


def test_request_limit_is_shared_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://dev-qatrack-api.dev.elicer.io/schedule"
    monkeypatch.setattr(Config, "MAX_REQUESTS", 2)
    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: FakeResponse())

    api_client.get(url, {})
    api_client.get(url, {})

    with pytest.raises(api_client.RequestLimitExceeded):
        api_client.get(url, {})

    assert api_client.request_count() == 2


def test_5xx_latches_abort_and_prevents_later_network_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://dev-qatrack-api.dev.elicer.io/schedule"
    network_calls = 0

    def fake_request(*args: Any, **kwargs: Any) -> FakeResponse:
        nonlocal network_calls
        network_calls += 1
        return FakeResponse(503, "unavailable")

    monkeypatch.setattr(requests, "request", fake_request)

    with pytest.raises(api_client.AbortTestError, match="service_unavailable") as exc_info:
        api_client.get(url, {})
    assert exc_info.value.status_code == 503
    assert exc_info.value.error_code == "service_unavailable"
    with pytest.raises(api_client.AbortTestError, match="이전 5xx"):
        api_client.get(url, {})

    assert network_calls == 1


def test_token_is_normalized_and_rejects_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # fallback 토큰만 테스트하기 위해 자동 로그인 정보 제거
    monkeypatch.delenv("LXP_LEARNER_EMAIL", raising=False)
    monkeypatch.delenv("LXP_LEARNER_PASSWORD", raising=False)

    monkeypatch.setattr(token_manager, "_learner_token_cache", None)
    monkeypatch.setenv("LXP_LEARNER_TOKEN", "Bearer learner-secret")

    assert token_manager.learner_auth_header() == {
        "Authorization": "Bearer learner-secret"
    }

    monkeypatch.setattr(token_manager, "_learner_token_cache", None)
    monkeypatch.setenv("LXP_LEARNER_TOKEN", "secret with-space")

    with pytest.raises(token_manager.TokenNotSetError) as exc_info:
        token_manager.get_learner_token()

    assert isinstance(
        exc_info.value.__cause__,
        token_manager.InvalidTokenError,
    )
