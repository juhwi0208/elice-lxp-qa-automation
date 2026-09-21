"""브라우저를 실행하지 않는 E2E 로그인 지원 코드 단위 테스트."""

from urllib.parse import parse_qs, urlparse

import pytest

from part3_e2e.config import (
    Credentials,
    E2EConfigurationError,
    E2ESettings,
    load_e2e_settings,
)
from part3_e2e.pages.login_page import build_login_url, build_logout_url


def test_login_url_contains_safe_redirect_and_org() -> None:
    settings = E2ESettings(
        accounts_base_url="https://dev-qatrack-accounts.dev.elicer.io",
        web_base_url="https://dev-qatrack-web.dev.elicer.io",
        org_name_short="academy",
    )

    parsed = urlparse(build_login_url(settings))
    query = parse_qs(parsed.query)

    assert parsed.path == "/accounts/signin/me"
    assert query["continue_to"] == ["https://dev-qatrack-web.dev.elicer.io/lxp"]
    assert query["org"] == ["academy"]
    assert query["lang"] == ["ko"]


def test_logout_url_contains_safe_redirect_and_org() -> None:
    settings = E2ESettings(
        accounts_base_url="https://dev-qatrack-accounts.dev.elicer.io",
        web_base_url="https://dev-qatrack-web.dev.elicer.io",
        org_name_short="academy",
    )

    parsed = urlparse(build_logout_url(settings))
    query = parse_qs(parsed.query)

    assert parsed.path == "/accounts/signout/me"
    assert query["continue_to"] == ["https://dev-qatrack-web.dev.elicer.io/lxp"]
    assert query["org"] == ["academy"]
    assert query["lang"] == ["ko"]


def test_e2e_settings_reject_external_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LXP_ORG_NAME_SHORT", "academy")
    monkeypatch.setenv("LXP_ACCOUNTS_BASE_URL", "https://example.com")

    with pytest.raises(E2EConfigurationError):
        load_e2e_settings()


def test_credentials_repr_redacts_password() -> None:
    credentials = Credentials(email="qa@example.com", password="top-secret")

    assert "qa@example.com" in repr(credentials)
    assert "top-secret" not in repr(credentials)
