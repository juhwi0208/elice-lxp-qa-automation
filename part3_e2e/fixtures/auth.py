"""역할별 Selenium 로그인과 인증 브라우저 fixture."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from part3_e2e.config import (
    Credentials,
    E2EConfigurationError,
    E2ESettings,
    load_credentials,
    load_e2e_settings,
)
from part3_e2e.pages.login_page import LoginPage


@pytest.fixture(scope="session")
def e2e_settings() -> E2ESettings:
    try:
        return load_e2e_settings()
    except E2EConfigurationError as exc:
        pytest.skip(str(exc))


def _credentials_or_skip(role: str) -> Credentials:
    try:
        return load_credentials(role)
    except E2EConfigurationError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def learner_credentials() -> Credentials:
    return _credentials_or_skip("learner")


@pytest.fixture(scope="session")
def educator_credentials() -> Credentials:
    return _credentials_or_skip("educator")


@pytest.fixture
def login_page(driver: WebDriver, e2e_settings: E2ESettings) -> LoginPage:
    return LoginPage(driver, e2e_settings)


def _authenticated_driver(
    factory: Callable[[], WebDriver],
    settings: E2ESettings,
    credentials: Credentials,
) -> Iterator[WebDriver]:
    driver = factory()
    try:
        LoginPage(driver, settings).login_and_wait(credentials)
        yield driver
    finally:
        driver.quit()


@pytest.fixture(scope="session")
def learner_authenticated_driver(
    selenium_driver_factory: Callable[[], WebDriver],
    e2e_settings: E2ESettings,
    learner_credentials: Credentials,
) -> Iterator[WebDriver]:
    yield from _authenticated_driver(
        selenium_driver_factory, e2e_settings, learner_credentials
    )


@pytest.fixture(scope="session")
def educator_authenticated_driver(
    selenium_driver_factory: Callable[[], WebDriver],
    e2e_settings: E2ESettings,
    educator_credentials: Credentials,
) -> Iterator[WebDriver]:
    yield from _authenticated_driver(
        selenium_driver_factory, e2e_settings, educator_credentials
    )
