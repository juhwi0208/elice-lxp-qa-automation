"""E2E 테스트 실패 시 스크린샷 저장과 Allure 첨부를 담당한다."""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Any

import allure
import pytest
from selenium.webdriver.remote.webdriver import WebDriver


SCREENSHOT_DIR = Path("artifacts/screenshots")


def _screenshots_enabled() -> bool:
    """실패 캡처는 로컬 진단이 필요할 때만 명시적으로 활성화한다."""
    return os.getenv("LXP_CAPTURE_FAILURE_SCREENSHOTS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _safe_filename(value: str) -> str:
    """pytest nodeid를 안전한 파일명으로 변환한다."""
    safe_name = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        value,
    ).strip("_")

    return safe_name or "unknown_test"


def _find_webdriver(item: pytest.Item) -> WebDriver | None:
    """
    현재 테스트에서 사용 중인 WebDriver fixture를 찾는다.

    fixture 이름에 의존하지 않고 item.funcargs 안에서
    실제 WebDriver 객체를 찾아 반환한다.

    예:
        driver
        learner_authenticated_driver
        educator_authenticated_driver
    """
    for fixture_value in item.funcargs.values():
        if isinstance(fixture_value, WebDriver):
            return fixture_value

    return None


def _save_viewport_screenshot(
    driver: WebDriver,
    screenshot_path: Path,
) -> bytes:
    """
    현재 브라우저에 보이는 viewport 화면을 캡처한다.

    테스트 실패 직후의 실제 브라우저 화면을 확인하는 용도다.
    """
    screenshot = driver.get_screenshot_as_png()
    screenshot_path.write_bytes(screenshot)

    return screenshot


def _capture_chromium_full_page(
    driver: WebDriver,
) -> bytes | None:
    """
    Chrome/Chromium/Edge 계열에서 CDP를 사용해
    현재 문서 전체 영역을 캡처한다.
    """
    execute_cdp_cmd = getattr(
        driver,
        "execute_cdp_cmd",
        None,
    )

    if not callable(execute_cdp_cmd):
        return None

    try:
        metrics = execute_cdp_cmd(
            "Page.getLayoutMetrics",
            {},
        )

        content_size = metrics.get("contentSize", {})

        width = int(content_size.get("width", 0))
        height = int(content_size.get("height", 0))

        if width <= 0 or height <= 0:
            return None

        result = execute_cdp_cmd(
            "Page.captureScreenshot",
            {
                "format": "png",
                "captureBeyondViewport": True,
                "fromSurface": True,
                "clip": {
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": height,
                    "scale": 1,
                },
            },
        )

        encoded_data = result.get("data")

        if not encoded_data:
            return None

        return base64.b64decode(encoded_data)

    except Exception as error:
        print(f"Chromium full-page screenshot failed: {error}")
        return None


def _capture_firefox_full_page(
    driver: WebDriver,
) -> bytes | None:
    """
    Firefox가 전체 페이지 스크린샷 API를 제공하는 경우 사용한다.
    """
    full_page_method = getattr(
        driver,
        "get_full_page_screenshot_as_png",
        None,
    )

    if not callable(full_page_method):
        return None

    try:
        return full_page_method()

    except Exception as error:
        print(f"Firefox full-page screenshot failed: {error}")
        return None


def _save_full_page_screenshot(
    driver: WebDriver,
    screenshot_path: Path,
) -> bytes | None:
    """
    브라우저 종류에 맞춰 전체 페이지 스크린샷을 캡처한다.

    Chrome/Chromium/Edge:
        Chrome DevTools Protocol 사용

    Firefox:
        Selenium 전체 페이지 스크린샷 API 사용

    지원되지 않거나 캡처에 실패하면 None을 반환한다.
    """
    browser_name = str(
        driver.capabilities.get(
            "browserName",
            "",
        )
    ).lower()

    screenshot: bytes | None = None

    if browser_name in {
        "chrome",
        "chromium",
        "msedge",
        "microsoftedge",
    }:
        screenshot = _capture_chromium_full_page(driver)

    elif browser_name == "firefox":
        screenshot = _capture_firefox_full_page(driver)

    if screenshot is None:
        return None

    screenshot_path.write_bytes(screenshot)

    return screenshot


def _attach_to_allure(
    screenshot: bytes,
    name: str,
) -> None:
    """PNG 스크린샷을 Allure 테스트 결과에 첨부한다."""
    allure.attach(
        screenshot,
        name=name,
        attachment_type=allure.attachment_type.PNG,
    )


def _capture_failure_screenshots(
    driver: WebDriver,
    test_name: str,
    attempt: int,
) -> None:
    """
    실패한 E2E 테스트의 증적을 저장한다.

    1. 실패 직후 현재 viewport
    2. 전체 페이지

    두 이미지를 로컬/Jenkins Artifact용 폴더에 저장하고
    Allure에도 함께 첨부한다.
    """
    SCREENSHOT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = _safe_filename(test_name)

    viewport_path = SCREENSHOT_DIR / f"{safe_name}_attempt_{attempt}_viewport.png"

    full_page_path = SCREENSHOT_DIR / f"{safe_name}_attempt_{attempt}_full_page.png"

    try:
        viewport_screenshot = _save_viewport_screenshot(
            driver,
            viewport_path,
        )

        _attach_to_allure(
            viewport_screenshot,
            name=(f"Failure Viewport - {safe_name} - attempt {attempt}"),
        )

        print(f"Failure viewport screenshot saved: {viewport_path}")

    except Exception as error:
        print(f"Failed to capture viewport screenshot: {error}")

    try:
        full_page_screenshot = _save_full_page_screenshot(
            driver,
            full_page_path,
        )

        if full_page_screenshot is None:
            print("Full-page screenshot is not supported or could not be captured.")
            return

        _attach_to_allure(
            full_page_screenshot,
            name=(f"Failure Full Page - {safe_name} - attempt {attempt}"),
        )

        print(f"Failure full-page screenshot saved: {full_page_path}")

    except Exception as error:
        print(f"Failed to capture full-page screenshot: {error}")


@pytest.hookimpl(
    hookwrapper=True,
    tryfirst=True,
)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[Any],
):
    """
    E2E 테스트의 call 단계가 실패하거나 rerun 대상이 되면
    Selenium 스크린샷을 자동으로 저장한다.

    fixture 이름과 관계없이 테스트에서 사용 중인
    WebDriver 객체를 찾아 적용한다.
    """
    outcome = yield
    report = outcome.get_result()

    if not _screenshots_enabled():
        return

    if report.when != "call":
        return

    if report.outcome not in {
        "failed",
        "rerun",
    }:
        return

    driver = _find_webdriver(item)

    if driver is None:
        return

    attempt = (
        getattr(
            item,
            "_failure_screenshot_attempt",
            0,
        )
        + 1
    )

    setattr(
        item,
        "_failure_screenshot_attempt",
        attempt,
    )

    _capture_failure_screenshots(
        driver=driver,
        test_name=item.nodeid,
        attempt=attempt,
    )
