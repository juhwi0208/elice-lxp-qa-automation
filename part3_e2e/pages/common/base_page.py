"""모든 LXP Selenium Page Object가 공유하는 브라우저 동작."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from selenium.webdriver.remote.webdriver import WebDriver

from part3_e2e.config import E2EConfigurationError, E2ESettings
from part3_e2e.pages.common.selenium_support import wait_url


def build_web_url(settings: E2ESettings, path: str = "/") -> str:
    normalized_path = f"/{path.lstrip('/')}"
    url = urljoin(f"{settings.web_base_url}/", normalized_path.lstrip("/"))
    if urlparse(url).netloc != urlparse(settings.web_base_url).netloc:
        raise E2EConfigurationError("E2E 이동 경로는 QA 웹 호스트 내부여야 합니다.")
    return url


class BasePage:
    def __init__(self, driver: WebDriver, settings: E2ESettings) -> None:
        self.driver = driver
        self.page = driver
        self.settings = settings

    def open(self, path: str = "/lxp") -> None:
        self.driver.get(build_web_url(self.settings, path))

    def reload(self) -> None:
        self.driver.refresh()

    def go_back(self) -> None:
        self.driver.back()

    def expect_path(self, path: str) -> None:
        wait_url(self.driver, build_web_url(self.settings, path))
