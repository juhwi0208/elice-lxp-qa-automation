"""Selenium WebDriver 생성과 종료를 담당하는 공통 fixture."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.remote.webdriver import WebDriver


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("selenium-e2e")
    group.addoption(
        "--selenium-browser",
        action="store",
        choices=("chrome", "chromium", "edge", "firefox"),
        default=os.getenv("LXP_SELENIUM_BROWSER", "chrome"),
        help="Selenium E2E 브라우저 (기본값: chrome)",
    )
    group.addoption(
        "--selenium-headed",
        action="store_true",
        default=False,
        help="Selenium 브라우저 창을 표시합니다.",
    )


def _chromedriver_service() -> ChromeService | None:
    """명시 경로, PATH, Selenium 캐시 순으로 ChromeDriver를 찾는다."""
    configured = os.getenv("LXP_CHROMEDRIVER_PATH", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))

    path_driver = shutil.which("chromedriver")
    if path_driver:
        candidates.append(Path(path_driver))

    cache_root = Path.home() / ".cache" / "selenium" / "chromedriver" / "win64"
    if cache_root.is_dir():
        candidates.extend(sorted(cache_root.glob("*/chromedriver.exe"), reverse=True))

    for candidate in candidates:
        if candidate.is_file():
            return ChromeService(executable_path=str(candidate.resolve()))
    return None


def _build_driver(browser_name: str, *, headed: bool) -> WebDriver:
    normalized = "chrome" if browser_name == "chromium" else browser_name

    if normalized == "chrome":
        options = webdriver.ChromeOptions()
        if not headed:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--incognito")
        service = _chromedriver_service()
        if service is not None:
            return webdriver.Chrome(service=service, options=options)
        return webdriver.Chrome(options=options)

    if normalized == "edge":
        options = webdriver.EdgeOptions()
        if not headed:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("-inprivate")
        return webdriver.Edge(options=options)

    options = webdriver.FirefoxOptions()
    if not headed:
        options.add_argument("-headless")
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1920, 1080)
    return driver


@pytest.fixture(scope="session")
def selenium_driver_factory(
    request: pytest.FixtureRequest,
) -> Callable[[], WebDriver]:
    browser_name = request.config.getoption("--selenium-browser")
    headed = request.config.getoption("--selenium-headed")

    def factory() -> WebDriver:
        driver = _build_driver(browser_name, headed=headed)
        driver.set_page_load_timeout(30)
        return driver

    return factory


@pytest.fixture
def driver(
    selenium_driver_factory: Callable[[], WebDriver],
) -> Iterator[WebDriver]:
    browser = selenium_driver_factory()
    try:
        yield browser
    finally:
        browser.quit()
