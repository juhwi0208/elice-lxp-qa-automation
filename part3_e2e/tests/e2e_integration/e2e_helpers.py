"""E2E 통합 테스트 공통 헬퍼 및 픽스처 모듈 (e2e_helpers.py).

홈, 과목, 일정, 게시판 4대 도메인 E2E 테스트에서 공유하는 픽스처와 헬퍼 함수를 정의한다.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlparse
from uuid import uuid4

import allure
import pytest
from selenium.common.exceptions import (
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select, WebDriverWait

from part1_api_automation.tests.board.helpers import article_get_url, multipart
from part1_api_automation.utils import api_client
from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.config import Config
from part1_api_automation.utils.token_manager import educator_auth_header, learner_auth_header

Config.MAX_REQUESTS = max(Config.MAX_REQUESTS, 2000)
from part3_e2e.config import ClassroomContext, CourseTestData, Credentials, E2ESettings
from part3_e2e.fixtures.tc_result_collector import TCResultCollector
from part3_e2e.pages.board_page import BoardPage
from part3_e2e.pages.class_schedule_page import ClassSchedulePage
from part3_e2e.pages.classroom_home_page import ClassroomHomePage, WidgetSnapshot
from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.common.base_page import build_web_url
from part3_e2e.pages.common.selenium_support import (
    accessible_name,
    click_when_ready,
    role_elements,
    text_elements,
    wait_text,
)
from part3_e2e.pages.course_detail_page import CourseDetailPage
from part3_e2e.pages.course_list_page import CourseListPage
from part3_e2e.pages.course_management_page import CourseManagementPage
from part3_e2e.pages.login_page import LoginPage
from test_support.cleanup import CleanupRegistry


_WAIT = 20
_SHORT_WAIT = 8
_QA_PREFIX = "[QA-AUTO]"

# 한 항목씩 실행을 막지 않도록, 이 통합 시나리오의 외부 기준 데이터는 시작 시
# 한 번에 누락 목록을 보여 준다. 값은 QA 1팀의 실제 데이터여야 하며 기본값으로
# 대체하지 않는다.
_INTEGRATION_REQUIRED_ENV = (
    "LXP_E2E_ATTACHMENT_PATH",
    "LXP_E2E_SCHEDULE_START",
    "LXP_E2E_SCHEDULE_END",
    "LXP_E2E_ALL_DAY_DATE",
    "LXP_E2E_RECURRING_UNTIL",
    "LXP_ALLOW_IRREVERSIBLE_TEST_RESET",
    "LXP_E2E_MULTI_SCHEDULE_TITLES",
    "LXP_QUIZ_RESPONSE_DELETE_PATH",
    "LXP_PRIMARY_CLASSROOM_NAME",
    "LXP_PRIMARY_CLASSROOM_MARKER",
    "LXP_E2E_TEMP_COURSE_NAME",
    "LXP_BOARD_ARTICLE_ID",
    "LXP_BASELINE_BOARD_TITLE",
    "LXP_OWN_COMMENT_TEXT",
    "LXP_OTHER_COMMENT_TEXT",
    "LXP_OTHER_COMMENT_OWNER",
    "LXP_LEARNER_DISPLAY_NAME",
    "LXP_BASELINE_SCHEDULE_TITLE",
    "LXP_BASELINE_SCHEDULE_DATE_TEXT",
    "LXP_LECTURE_ID",
    "LXP_LEARNER_USER_ID",
    "LXP_MATERIAL_QUIZ_ID",
    "LXP_TEST_QUESTION_COUNT",
    "LXP_EXPECTED_LESSON_COUNT",
    "LXP_EXPECTED_MATERIAL_COUNT",
    "LXP_EXPECTED_TEST_NUMBER_TEXT",
    "LXP_TEST_TIME_LIMIT_TEXT",
)


@dataclass(frozen=True)
class IntegrationData:
    primary_class_name: str
    primary_class_marker: str
    temporary_course_name: str
    baseline_board_article_id: int
    baseline_board_title: str
    own_comment_text: str
    other_comment_text: str
    other_comment_owner: str
    learner_display_name: str
    baseline_schedule_title: str
    baseline_schedule_date_text: str
    attachment_path: Path
    schedule_start: datetime
    schedule_end: datetime
    all_day_date: datetime
    recurring_until: datetime
    empty_period_moves: int
    multi_schedule_titles: tuple[str, ...]
    api_base_url: str
    classroom_api_base_url: str
    org_name_short: str
    lecture_id: int
    learner_user_id: int
    material_quiz_id: int
    quiz_response_delete_path: str
    test_question_count: int
    expected_lesson_count: int
    expected_material_count: int
    expected_test_number_text: str
    test_time_limit_text: str


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.fail(f"Excel 1~98 사전 데이터 환경변수 미설정: {name}", pytrace=False)
    return value


def _require_integration_preconditions() -> None:
    missing = [name for name in _INTEGRATION_REQUIRED_ENV if not os.getenv(name, "").strip()]
    if missing:
        pytest.fail(
            "Excel 1~98에 필요한 QA 1팀 기준 데이터 환경변수 미설정: "
            + ", ".join(missing),
            pytrace=False,
        )


def _positive_int(name: str) -> int:
    try:
        value = int(_required(name))
    except ValueError:
        pytest.fail(f"{name}은 양의 정수여야 합니다.", pytrace=False)
    if value <= 0:
        pytest.fail(f"{name}은 양의 정수여야 합니다.", pytrace=False)
    return value


def _iso_datetime(name: str) -> datetime:
    try:
        return datetime.fromisoformat(_required(name))
    except ValueError:
        pytest.fail(f"{name}은 ISO 8601 일시여야 합니다.", pytrace=False)


def _qa_url(name: str) -> str:
    value = _required(name).rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".dev.elicer.io"):
        pytest.fail(f"{name}은 승인된 HTTPS QA URL이어야 합니다.", pytrace=False)
    if parsed.username or parsed.password or parsed.fragment:
        pytest.fail(f"{name}에 사용자 정보나 fragment를 넣을 수 없습니다.", pytrace=False)
    return value


def _qa_url_or(name: str, fallback_name: str) -> str:
    """전용 클래스 API URL이 없으면 이미 검증된 기본 QA API URL을 사용한다."""
    return _qa_url(name) if os.getenv(name, "").strip() else _qa_url(fallback_name)


def _wait_page_loaded(page) -> None:
    """각 Page Object가 제공하는 실제 로드 대기 API를 사용한다."""
    if isinstance(page, ClassSchedulePage):
        page.wait_until_loaded()
    else:
        page.expect_loaded()


@pytest.fixture(scope="module")
def integration_state() -> dict:
    """하위 conftest의 function fixture를 이 모듈에서 module scope로 재정의한다."""
    return {}


@pytest.fixture(scope="module")
def integration_cleanup() -> CleanupRegistry:
    registry = CleanupRegistry()
    yield registry
    registry.run()


@pytest.fixture(scope="session")
def integration_data(classroom_context: ClassroomContext) -> IntegrationData:
    _require_integration_preconditions()
    attachment = Path(_required("LXP_E2E_ATTACHMENT_PATH")).expanduser()
    if not attachment.is_file() or attachment.stat().st_size > 1024 * 1024:
        pytest.fail(f"1MiB 이하 소형 첨부 fixture가 필요합니다: {attachment}", pytrace=False)
    start = _iso_datetime("LXP_E2E_SCHEDULE_START")
    end = _iso_datetime("LXP_E2E_SCHEDULE_END")
    until = _iso_datetime("LXP_E2E_RECURRING_UNTIL")
    all_day = _iso_datetime("LXP_E2E_ALL_DAY_DATE")
    if start.tzinfo is None or end.tzinfo is None or until.tzinfo is None or all_day.tzinfo is None:
        pytest.fail("일정 ISO 8601 값에는 QA 클래스 시간대 오프셋이 필요합니다.", pytrace=False)
    if end <= start or until.date() < start.date():
        pytest.fail("일정 시작/종료/반복 종료 사전조건이 올바르지 않습니다.", pytrace=False)
    if os.getenv("LXP_ALLOW_IRREVERSIBLE_TEST_RESET", "").strip().lower() != "true":
        pytest.fail("응시 원복 승인값 LXP_ALLOW_IRREVERSIBLE_TEST_RESET=true가 필요합니다.")
    multi_titles = tuple(x.strip() for x in _required("LXP_E2E_MULTI_SCHEDULE_TITLES").split("|") if x.strip())
    if len(multi_titles) < 2:
        pytest.fail("복수 일정 제목을 |로 구분해 두 개 이상 지정해야 합니다.")
    delete_path = _required("LXP_QUIZ_RESPONSE_DELETE_PATH").strip("/")
    if not delete_path.startswith("material_quiz/response/") or ".." in delete_path:
        pytest.fail("퀴즈 응답 삭제 경로가 허용 범위를 벗어났습니다.")
    return IntegrationData(
        primary_class_name=_required("LXP_PRIMARY_CLASSROOM_NAME"),
        primary_class_marker=_required("LXP_PRIMARY_CLASSROOM_MARKER"),
        temporary_course_name=_required("LXP_E2E_TEMP_COURSE_NAME"),
        baseline_board_article_id=_positive_int("LXP_BOARD_ARTICLE_ID"),
        baseline_board_title=_required("LXP_BASELINE_BOARD_TITLE"),
        own_comment_text=_required("LXP_OWN_COMMENT_TEXT"),
        other_comment_text=_required("LXP_OTHER_COMMENT_TEXT"),
        other_comment_owner=_required("LXP_OTHER_COMMENT_OWNER"),
        learner_display_name=_required("LXP_LEARNER_DISPLAY_NAME"),
        baseline_schedule_title=_required("LXP_BASELINE_SCHEDULE_TITLE"),
        baseline_schedule_date_text=_required("LXP_BASELINE_SCHEDULE_DATE_TEXT"),
        attachment_path=attachment.resolve(),
        schedule_start=start,
        schedule_end=end,
        all_day_date=all_day,
        recurring_until=until,
        empty_period_moves=_positive_int("LXP_E2E_EMPTY_PERIOD_MOVES"),
        multi_schedule_titles=multi_titles,
        api_base_url=_qa_url_or("LXP_LEGACY_API_BASE_URL", "LXP_API_BASE_URL"),
        classroom_api_base_url=_qa_url_or("LXP_CLASSROOM_API_BASE_URL", "LXP_API_BASE_URL"),
        org_name_short=_required("LXP_ORG_NAME_SHORT"),
        lecture_id=_positive_int("LXP_LECTURE_ID"),
        learner_user_id=_positive_int("LXP_LEARNER_USER_ID"),
        material_quiz_id=_positive_int("LXP_MATERIAL_QUIZ_ID"),
        quiz_response_delete_path=delete_path,
        test_question_count=_positive_int("LXP_TEST_QUESTION_COUNT"),
        expected_lesson_count=_positive_int("LXP_EXPECTED_LESSON_COUNT"),
        expected_material_count=_positive_int("LXP_EXPECTED_MATERIAL_COUNT"),
        expected_test_number_text=_required("LXP_EXPECTED_TEST_NUMBER_TEXT"),
        test_time_limit_text=_required("LXP_TEST_TIME_LIMIT_TEXT"),
    )


@pytest.fixture(scope="session")
def admin_app_shell(
    selenium_driver_factory,
    e2e_settings: E2ESettings,
    classroom_context: ClassroomContext,
    educator_credentials: Credentials,
) -> AppShell:
    """전용 관리자 계정 없이 교육자 QA 계정으로 관리자 UI를 확인한다."""
    driver = selenium_driver_factory()
    try:
        LoginPage(driver, e2e_settings).login_and_wait(educator_credentials)
        yield AppShell(driver, e2e_settings, classroom_context)
    finally:
        driver.quit()


def _headers(data: IntegrationData, *, educator: bool = False) -> dict:
    headers = educator_auth_header() if educator else learner_auth_header()
    headers["x-elice-org-name-short"] = data.org_name_short
    return headers


def _ok(response) -> dict:
    assert response.status_code == 200, f"HTTP {response.status_code}: {response.text[:300]}"
    body = response.json()
    if isinstance(body, dict) and isinstance(body.get("_result"), dict):
        assert body["_result"].get("status") == "ok", body
    return body


def _visible(scope, by: str, value: str) -> list[WebElement]:
    elements = []
    for e in scope.find_elements(by, value):
        try:
            if e.is_displayed():
                elements.append(e)
        except (StaleElementReferenceException, Exception):
            continue
    return elements


def _body(driver: WebDriver, timeout: float = 3.0) -> str:
    def get_text(d):
        try:
            t = d.find_element(By.TAG_NAME, "body").text.strip()
            return t if t else False
        except Exception:
            return False
    try:
        return WebDriverWait(driver, timeout).until(get_text)
    except TimeoutException:
        value = driver.find_element(By.TAG_NAME, "body").text.strip()
        assert value, "화면 본문이 비어 있습니다."
        return value


def _lines(value: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in value.splitlines() if line.strip())


def _unique(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


def _set_text(element: WebElement, value: str) -> None:
    element.click()
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(Keys.BACKSPACE)
    element.send_keys(value)


def _click_named(scope, driver: WebDriver, pattern: str, *, role: str = "button") -> WebElement:
    matcher = re.compile(pattern, re.I)
    # SPA rerenders commonly invalidate a previously collected button. Search
    # the live DOM immediately before the click and ignore stale candidates.
    selector = "button,[role='button'],[role='tab']" if role == "button" else f"[role='{role}']"
    matches = []
    for element in scope.find_elements(By.CSS_SELECTOR, selector):
        try:
            if element.is_displayed() and element.is_enabled():
                acc_name = accessible_name(element)
                el_text = element.text.strip()
                if matcher.search(acc_name) or matcher.search(el_text):
                    matches.append(element)
        except StaleElementReferenceException:
            continue
    if not matches and role == "button":
        for element in scope.find_elements(By.XPATH, f"//*[self::button or @role='button' or @role='tab'][contains(., '{pattern}')]"):
            try:
                if element.is_displayed() and element.is_enabled():
                    matches.append(element)
            except StaleElementReferenceException:
                continue
    assert matches, f"{role} /{pattern}/ 요소를 찾지 못했습니다."
    click_when_ready(driver, matches[0])
    return matches[0]


def _ancestor(driver: WebDriver, element: WebElement) -> WebElement:
    result = driver.execute_script(
        "return arguments[0].closest('a,button,input,select,textarea,[role=button],[role=link],[tabindex]:not([tabindex=\"-1\"])') || arguments[0];",
        element,
    )
    assert result is not None
    return result


def _widget(home: ClassroomHomePage, title: str) -> WebElement:
    element = home._widget(title)
    assert element.is_displayed()
    return element


def _widget_click(home: ClassroomHomePage, title: str, text: str) -> None:
    matches = [e for e in text_elements(_widget(home, title), text, exact=False) if e.is_displayed()]
    assert matches, f"{title!r} 위젯에서 {text!r}을 찾지 못했습니다."
    click_when_ready(home.driver, _ancestor(home.driver, min(matches, key=lambda e: len(e.text))))


def _widget_view_all(home: ClassroomHomePage, title: str) -> None:
    candidates = [
        e for e in _widget(home, title).find_elements(By.XPATH, ".//a|.//button|.//*[@role='link']|.//*[@role='button']")
        if e.is_displayed() and re.search(r"전체\s*보기|더\s*보기", accessible_name(e))
    ]
    assert candidates, f"{title!r} 위젯의 전체 보기 요소를 찾지 못했습니다."
    click_when_ready(home.driver, candidates[0])


def _assert_widget_layout(home: ClassroomHomePage) -> None:
    widgets = {title: _widget(home, title) for title in home.WIDGET_TITLES}
    for title, element in widgets.items():
        assert element.rect["width"] > 0 and element.rect["height"] > 0, f"{title} 위젯 크기가 0입니다."
    pairs = list(widgets.items())
    for index, (left_name, left) in enumerate(pairs):
        for right_name, right in pairs[index + 1 :]:
            a, b = left.rect, right.rect
            overlap = not (
                a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
            )
            assert not overlap, f"위젯 겹침: {left_name}={a}, {right_name}={b}"


_CAPTURE_SCRIPT = r"""
(() => {
 const evidence=[]; Object.defineProperty(window,'__qaHttpEvidence',{configurable:true,value:evidence});
 const push=(url,status,transport,body)=>evidence.push({url:new URL(url,location.href).href,status,transport,body:String(body).slice(0,200000)});
 const originalFetch=window.fetch.bind(window);
 window.fetch=async function(input,init){const response=await originalFetch(input,init);const raw=typeof input==='string'?input:input.url;response.clone().text().then(body=>push(raw,response.status,'fetch',body));return response;};
 const originalOpen=XMLHttpRequest.prototype.open, originalSend=XMLHttpRequest.prototype.send;
 XMLHttpRequest.prototype.open=function(method,url){this.__qaUrl=url;return originalOpen.apply(this,arguments);};
 XMLHttpRequest.prototype.send=function(){this.addEventListener('loadend',()=>push(this.__qaUrl,this.status,'xhr',this.responseText||''));return originalSend.apply(this,arguments);};
})();
"""


_FAIL_SCRIPT = r"""
(() => {
 const target=%s,evidence=[]; Object.defineProperty(window,'__qaFaultEvidence',{configurable:true,value:evidence});
 const matches=raw=>new URL(raw,location.href).href===target;
 const record=(raw,transport)=>evidence.push({url:new URL(raw,location.href).href,status:500,transport});
 const originalFetch=window.fetch.bind(window);
 window.fetch=function(input,init){const raw=typeof input==='string'?input:input.url;if(!matches(raw))return originalFetch(input,init);record(raw,'fetch');return Promise.resolve(new Response('{"detail":"QA injected 500"}',{status:500,headers:{'Content-Type':'application/json'}}));};
 const originalOpen=XMLHttpRequest.prototype.open, originalSend=XMLHttpRequest.prototype.send;
 XMLHttpRequest.prototype.open=function(method,url){this.__qaUrl=url;return originalOpen.apply(this,arguments);};
 XMLHttpRequest.prototype.send=function(){if(!matches(this.__qaUrl))return originalSend.apply(this,arguments);record(this.__qaUrl,'xhr');Object.defineProperties(this,{readyState:{configurable:true,value:4},status:{configurable:true,value:500},statusText:{configurable:true,value:'Internal Server Error'},responseText:{configurable:true,value:'{"detail":"QA injected 500"}'},response:{configurable:true,value:'{"detail":"QA injected 500"}'}});queueMicrotask(()=>{this.dispatchEvent(new Event('readystatechange'));this.dispatchEvent(new ProgressEvent('load'));this.dispatchEvent(new ProgressEvent('loadend'));});};
})();
"""


def _add_script(driver: WebDriver, source: str) -> str:
    assert hasattr(driver, "execute_cdp_cmd"), "단계 10은 Chrome/Edge CDP가 필요합니다."
    return driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": source})["identifier"]


def _remove_script(driver: WebDriver, identifier: str) -> None:
    driver.execute_cdp_cmd("Page.removeScriptToEvaluateOnNewDocument", {"identifier": identifier})


def _capture_requests(home: ClassroomHomePage) -> list[dict]:
    driver = home.driver
    identifier = _add_script(driver, _CAPTURE_SCRIPT)
    try:
        driver.refresh()
        home.expect_all_widgets_visible()
        WebDriverWait(driver, _SHORT_WAIT).until(
            lambda d: len(d.execute_script("return window.__qaHttpEvidence || []")) >= 3
        )
        return driver.execute_script("return (window.__qaHttpEvidence || []).slice()")
    finally:
        _remove_script(driver, identifier)


_WEEKDAY_LABELS = frozenset({"일", "월", "화", "수", "목", "금", "토", "Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"})


def _normalized_home_snapshots(snapshots: dict[str, WidgetSnapshot]) -> dict[str, WidgetSnapshot]:
    """로캘 요일 축과 테스트 실행 중 정리되는 QA 임시글을 비교에서 제외한다."""
    normalized: dict[str, WidgetSnapshot] = {}
    for title, snapshot in snapshots.items():
        lines = [line for line in snapshot.lines if line not in _WEEKDAY_LABELS]
        if title == ClassroomHomePage.SCHEDULE_WIDGET:
            # 종일 QA 일정은 이전 실패 실행의 정리 시점에 따라 위젯에 잠시 남을 수 있다.
            lines = [line for line in lines if line != "하루종일" and not line.startswith(_QA_PREFIX)]
        if title == ClassroomHomePage.BOARD_WIDGET:
            retained: list[str] = []
            index = 0
            while index < len(lines):
                if lines[index].startswith(_QA_PREFIX):
                    index += 2  # 게시판 위젯은 제목 다음에 등록일을 표시한다.
                    continue
                retained.append(lines[index])
                index += 1
            lines = retained
        normalized[title] = WidgetSnapshot(snapshot.title, tuple(lines))
    return normalized


def _loaded_home_snapshots(home: ClassroomHomePage) -> dict[str, WidgetSnapshot]:
    """달력 뼈대가 아닌 일정 데이터까지 렌더링된 홈 스냅샷을 반환한다."""
    def loaded(_: WebDriver) -> dict[str, WidgetSnapshot] | bool:
        snapshots = home.snapshots()
        schedule_lines = snapshots[ClassroomHomePage.SCHEDULE_WIDGET].lines
        return snapshots if any(
            line.startswith("오늘") or line == "예정된 일정이 없습니다" or "오전" in line or "오후" in line
            for line in schedule_lines
        ) else False

    return WebDriverWait(home.driver, _WAIT).until(loaded)


def _expect_home_snapshots(home: ClassroomHomePage, expected: dict[str, WidgetSnapshot]) -> None:
    normalized_expected = _normalized_home_snapshots(expected)
    try:
        WebDriverWait(home.driver, _WAIT).until(
            lambda _: _normalized_home_snapshots(home.snapshots()) == normalized_expected
        )
    except Exception as error:
        actual = _normalized_home_snapshots(home.snapshots())
        raise AssertionError(f"홈 위젯 스냅샷 불일치: expected={normalized_expected}, actual={actual}") from error
    assert _normalized_home_snapshots(home.snapshots()) == normalized_expected


def _expect_schedule_detail_title(driver: WebDriver, expected: str) -> None:
    """페이지 제목이 아닌, 열린 일정 상세 패널의 제목을 확인한다."""
    def matching_headings(_: WebDriver):
        return [
            element
            for element in _visible(driver, By.CSS_SELECTOR, "h1,h2,h3,h4,h5,h6,[role='heading']")
            if element.text.strip() == expected
        ] or False

    try:
        WebDriverWait(driver, _SHORT_WAIT).until(matching_headings)
    except TimeoutException as error:
        raise AssertionError(f"일정 상세 제목 {expected!r}을 찾지 못했습니다.") from error


def _close_schedule_detail(driver: WebDriver, title: str) -> None:
    """열린 상세 제목과 같은 패널의 마지막 제어(닫기)만 클릭한다."""
    heading = next(
        element
        for element in _visible(driver, By.CSS_SELECTOR, "h1,h2,h3,h4,h5,h6,[role='heading']")
        if element.text.strip() == title
    )
    panel = driver.execute_script(
        """
        let node = arguments[0];
        while (node && node !== document.body) {
            if (node.matches('[role=dialog],.MuiPopover-paper,.MuiDialog-paper')) return node;
            if (node.querySelectorAll(':scope button').length >= 3) return node;
            node = node.parentElement;
        }
        return null;
        """,
        heading,
    )
    assert panel is not None, f"일정 상세 패널을 찾지 못했습니다: {title!r}"
    controls = _visible(panel, By.CSS_SELECTOR, "button")
    assert controls, f"일정 상세 제어를 찾지 못했습니다: {title!r}"
    close = next(
        (
            button for button in controls
            if re.search(r"닫기|close|xmark", accessible_name(button) + " " + (button.get_attribute("innerHTML") or ""), re.I)
        ),
        controls[-1],
    )
    driver.execute_script("arguments[0].click()", close)
    WebDriverWait(driver, _SHORT_WAIT).until(
        lambda _: not any(
            element.text.strip() == title
            for element in _visible(driver, By.CSS_SELECTOR, "h1,h2,h3,h4,h5,h6,[role='heading']")
        )
    )


def _request_containing(evidence: list[dict], value: str, label: str) -> str:
    matches = {item["url"] for item in evidence if item.get("status") == 200 and value in item.get("body", "")}
    urls = sorted({item.get("url", "") for item in evidence})
    assert len(matches) == 1, f"{label} 기준값 {value!r}을 포함한 실제 조회 URL이 하나가 아닙니다: {matches}; captured={urls}"
    return next(iter(matches))


def _request_exact_path(evidence: list[dict], path: str, label: str) -> str:
    matches = {
        item["url"]
        for item in evidence
        if item.get("status") == 200 and urlparse(item.get("url", "")).path.rstrip("/") == path.rstrip("/")
    }
    assert len(matches) == 1, f"{label} 실제 조회 URL이 하나가 아닙니다: {matches}"
    return next(iter(matches))


def _assert_widget_failure(home: ClassroomHomePage, exact_url: str, failed: str, baseline: dict[str, WidgetSnapshot]) -> None:
    driver = home.driver
    identifier = _add_script(driver, _FAIL_SCRIPT % json.dumps(exact_url))
    try:
        driver.refresh()
        evidence = WebDriverWait(driver, _WAIT).until(
            lambda d: d.execute_script("return (window.__qaFaultEvidence || []).slice()") or False
        )
        assert all(item["url"] == exact_url and item["status"] == 500 for item in evidence)
        for title, expected in baseline.items():
            if title != failed:
                expected_snapshot = _normalized_home_snapshots({title: expected})
                WebDriverWait(driver, _WAIT).until(
                    lambda _: _normalized_home_snapshots({title: home.snapshot(title)}) == expected_snapshot
                )
        failed_text = _widget(home, failed).text
        assert re.search(r"오류|에러|다시\s*시도|불러오지|실패", failed_text, re.I)
        allure.attach(json.dumps(evidence, ensure_ascii=False, indent=2), name=f"단계10_{failed}_500증거", attachment_type=allure.attachment_type.JSON)
    finally:
        _remove_script(driver, identifier)
        driver.refresh()
        _expect_home_snapshots(home, baseline)


def _assert_common_home_failure(home: ClassroomHomePage, exact_url: str, baseline: dict[str, WidgetSnapshot]) -> None:
    """홈 공통 클래스 조회 500 주입 증거와 정상 새로고침 복구를 검증한다."""
    driver = home.driver
    identifier = _add_script(driver, _FAIL_SCRIPT % json.dumps(exact_url))
    try:
        driver.refresh()
        evidence = WebDriverWait(driver, _WAIT).until(
            lambda d: d.execute_script("return (window.__qaFaultEvidence || []).slice()") or False
        )
        assert all(item["url"] == exact_url and item["status"] == 500 for item in evidence)
    finally:
        _remove_script(driver, identifier)
        driver.refresh()
        _expect_home_snapshots(home, baseline)


def _course_names(driver: WebDriver) -> tuple[str, ...]:
    cards = _visible(driver, By.CSS_SELECTOR, "main button:has(img),main a:has(img),main [role='button']:has(img)")
    return _unique(card.text.splitlines()[0] for card in cards if card.text.strip())


def _add_course(mgmt: CourseManagementPage, name: str, existing_body: str) -> tuple[str, str]:
    _click_named(mgmt.driver, mgmt.driver, r"과목\s*추가|새\s*과목")
    dialogs = WebDriverWait(mgmt.driver, _SHORT_WAIT).until(
        lambda d: _visible(d, By.CSS_SELECTOR, "[role='dialog'],.MuiDialog-paper") or "/import" in d.current_url
    )
    if dialogs is True:  # import 화면은 모달 대신 과목 카드 목록을 제공한다.
        scope = mgmt.driver
    else:
        scope = dialogs[-1]
        searches = _visible(scope, By.CSS_SELECTOR, "input[type='search'],input[placeholder*='검색']")
        if searches:
            _set_text(searches[0], name)
            searches[0].send_keys(Keys.RETURN)
    target = wait_text(mgmt.driver, scope, name, exact=True, timeout=_SHORT_WAIT)
    container = mgmt.driver.execute_script(
        """
        let node = arguments[0];
        while (node && node !== document.body) {
            if (node.querySelector('input[type=checkbox],input[type=radio]')) return node;
            node = node.parentElement;
        }
        return arguments[0];
        """,
        target,
    )
    images = container.find_elements(By.TAG_NAME, "img")
    thumbnail = images[0].get_attribute("src") if images else ""
    controls = container.find_elements(By.CSS_SELECTOR, "input[type='checkbox'],input[type='radio']")
    mgmt.driver.execute_script("arguments[0].click()", controls[0] if controls else container)
    _click_named(scope, mgmt.driver, r"선택한\s*과목\s*추가|^(추가|저장|확인)$")
    WebDriverWait(mgmt.driver, _WAIT).until(lambda _: mgmt.card(name).is_displayed())
    return name, thumbnail


def _delete_course(mgmt: CourseManagementPage, name: str) -> None:
    mgmt.open()
    exact = [e for e in text_elements(mgmt.driver, name, exact=True) if e.is_displayed()]
    if not exact:
        return
    label = exact[-1]
    # 카드 제목과 더보기 버튼이 형제인 화면도 있어, 제목부터 상위 카드까지
    # 단계적으로 탐색한다.
    candidates = mgmt.driver.execute_script(
        """
        const out = []; let node = arguments[0];
        for (let depth = 0; node && depth < 7; depth++, node = node.parentElement) {
          out.push(...node.querySelectorAll('button,[role=button]'));
        }
        return [...new Set(out)];
        """, label,
    )
    more = [e for e in candidates if e.is_displayed() and (
        re.search(r"더보기|메뉴|설정|more", accessible_name(e), re.I)
        or e.find_elements(By.CSS_SELECTOR, "svg[data-testid*='More'],svg[data-icon='ellipsis']")
    )]
    if not more:
        debug = mgmt.driver.execute_script(
            """
            return [...arguments[0].parentElement.querySelectorAll('button,[role=button]')]
              .map(e => ({text:e.innerText, aria:e.getAttribute('aria-label'), title:e.getAttribute('title'), html:e.outerHTML.slice(0, 250)}));
            """, label,
        )
        raise AssertionError(f"{name!r} 과목 삭제 메뉴를 찾지 못했습니다: {debug!r}")
    click_when_ready(mgmt.driver, more[-1])
    _click_named(mgmt.driver, mgmt.driver, r"삭제|제거")
    dialogs = _visible(mgmt.driver, By.CSS_SELECTOR, "[role='dialog'],.MuiDialog-paper")
    _click_named(dialogs[-1] if dialogs else mgmt.driver, mgmt.driver, r"^(삭제|제거|확인)$")
    WebDriverWait(mgmt.driver, _WAIT).until(lambda _: not [e for e in text_elements(mgmt.driver, name, exact=True) if e.is_displayed()])


def _course_intro(mgmt: CourseManagementPage, course: str, value: str | None) -> str | None:
    mgmt.open(); mgmt.open_course(course)
    # 과목 상세의 '과목 설정'은 기본 정보 설정 화면으로 이동한다. 이 화면의
    # 두 번째 텍스트 입력란이 한 줄 소개다(첫 번째는 과목명).
    settings_items = [
        element
        for element in mgmt.driver.find_elements(By.XPATH, "//a[normalize-space()='과목 설정']")
        if element.is_displayed() and element.is_enabled()
    ]
    assert settings_items, "과목 상세에 '과목 설정' 이동 항목이 필요합니다."
    settings_url = settings_items[0].get_attribute("href")
    assert settings_url and re.search(r"/courses/\d+/manage$", settings_url), "과목 설정 링크 URL 형식이 올바르지 않습니다."
    click_when_ready(mgmt.driver, settings_items[0])
    # SPA 링크 클릭이 URL만 바꾸고 화면을 갱신하지 않는 경우가 있어, 실제 링크로
    # 이동한 뒤 입력란 렌더링 자체를 대기 기준으로 삼는다.
    mgmt.driver.get(settings_url)
    fields = WebDriverWait(mgmt.driver, _WAIT).until(
        lambda d: [field for field in _visible(d, By.CSS_SELECTOR, "textarea,input[type='text']") if field.is_enabled()] or False
    )
    assert len(fields) >= 2, "기본 정보 설정 화면에 과목명·한 줄 소개 입력란이 필요합니다."
    introduction_field = fields[1]
    original = introduction_field.get_attribute("value") or introduction_field.text or ""
    target = original if value is None else value
    _set_text(introduction_field, target)
    _click_named(mgmt.driver, mgmt.driver, r"^(저장|완료|확인)$")
    # 저장 결과는 목록 본문에 즉시 노출되지 않을 수 있다. 같은 기본 정보
    # 입력란의 값이 저장된 값을 다시 읽을 수 있는지를 확인한다.
    WebDriverWait(mgmt.driver, _WAIT).until(
        lambda d: len(
            [
                field
                for field in _visible(d, By.CSS_SELECTOR, "textarea,input[type='text']")
                if field.is_enabled()
            ]
        ) >= 2
        and [
            field
            for field in _visible(d, By.CSS_SELECTOR, "textarea,input[type='text']")
            if field.is_enabled()
        ][1].get_attribute("value") == target
    )
    return original


def _course_order(mgmt: CourseManagementPage) -> tuple[str, ...]:
    mgmt.open()
    def cards_loaded(_: WebDriver) -> tuple[str, ...] | bool:
        names = _course_names(mgmt.driver)
        return names if len(names) >= 2 else False

    return WebDriverWait(mgmt.driver, _WAIT).until(cards_loaded)


def _swap_courses(mgmt: CourseManagementPage) -> tuple[tuple[str, ...], tuple[str, ...]]:
    before = _course_order(mgmt)
    _click_named(mgmt.driver, mgmt.driver, r"순서\s*변경")
    cards = _visible(mgmt.driver, By.CSS_SELECTOR, "main [draggable=true],[role='dialog'] [draggable=true],main li:has(img)")
    if len(cards) < 2:
        return before, before
    ActionChains(mgmt.driver).drag_and_drop(cards[0], cards[1]).perform()
    _click_named(mgmt.driver, mgmt.driver, r"^(저장|완료|확인)$")
    after = _course_order(mgmt)
    assert before != after and sorted(before) == sorted(after)
    return before, after


def _restore_order(mgmt: CourseManagementPage, expected: tuple[str, ...]) -> None:
    if _course_order(mgmt) == expected:
        return
    _click_named(mgmt.driver, mgmt.driver, r"순서\s*변경")
    cards = _visible(mgmt.driver, By.CSS_SELECTOR, "main [draggable=true],[role='dialog'] [draggable=true],main li:has(img)")
    if len(cards) < 2:
        return
    ActionChains(mgmt.driver).drag_and_drop(cards[1], cards[0]).perform()
    _click_named(mgmt.driver, mgmt.driver, r"^(저장|완료|확인)$")
    assert _course_order(mgmt) == expected


def _schedule_list(data: IntegrationData, classroom_id: str, *, educator: bool) -> list[dict]:
    response = api_client.get(
        f"{data.classroom_api_base_url}/schedule",
        headers=_headers(data, educator=educator),
        params={
            "classroom_id": classroom_id,
            "count": 50,
            "dt_start_ge": "2020-01-01T00:00:00+09:00",
            "dt_start_le": "2030-12-31T23:59:59+09:00",
        },
    )
    body = _ok(response)
    assert isinstance(body, list)
    return body


def _schedule_matches(data: IntegrationData, classroom_id: str, title: str, *, educator: bool) -> list[dict]:
    return [item for item in _schedule_list(data, classroom_id, educator=educator) if item.get("summary") == title]


def _delete_schedule(data: IntegrationData, classroom_id: str, schedule_id: int | str) -> None:
    if all(item.get("id") != schedule_id for item in _schedule_list(data, classroom_id, educator=True)):
        return
    response = api_client.delete(f"{data.classroom_api_base_url}/schedule/{schedule_id}", headers=_headers(data, educator=True), json={"classroom_id": classroom_id}, confirmed=True)
    _ok(response)
    assert all(item.get("id") != schedule_id for item in _schedule_list(data, classroom_id, educator=True))


def _classroom_courses(data: IntegrationData, classroom_id: str) -> list[dict]:
    response = api_client.get(
        f"{data.classroom_api_base_url}/classroom/{classroom_id}/course",
        headers=_headers(data, educator=True),
        params={"skip": 0, "count": 100},
    )
    assert response.status_code == 200, f"강의실 과목 조회 실패: HTTP {response.status_code}"
    body = response.json()
    assert isinstance(body, list), f"강의실 과목 조회 형식 오류: {body!r}"
    return body


def _delete_temporary_courses(data: IntegrationData, classroom_id: str, title: str) -> None:
    """QA 실행이 추가한 동일 제목의 1팀 과목 연결만 API로 원복한다."""
    for item in _classroom_courses(data, classroom_id):
        if str(item.get("title", "")) != title:
            continue
        course_id = item.get("course_id")
        assert isinstance(course_id, int), f"QA 임시 과목 ID 형식 오류: {item!r}"
        response = api_client.delete(
            f"{data.classroom_api_base_url}/classroom/{classroom_id}/course/{course_id}",
            headers=_headers(data, educator=True),
            confirmed=True,
        )
        assert response.status_code == 200, f"QA 임시 과목 삭제 실패: HTTP {response.status_code}"
    assert not [item for item in _classroom_courses(data, classroom_id) if str(item.get("title", "")) == title]


def _native(driver: WebDriver, element: WebElement, value: str) -> None:
    driver.execute_script("const e=arguments[0],v=arguments[1],p=Object.getPrototypeOf(e);Object.getOwnPropertyDescriptor(p,'value').set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));", element, value)


def _input_value_matches(element: WebElement, expected: datetime, *, date_only: bool) -> bool:
    """브라우저/로케일별 날짜·시간 표시 형식을 정규화해 비교한다."""
    raw = (element.get_attribute("value") or "").strip()
    if date_only:
        digits = re.findall(r"\d+", raw)
        if len(digits) >= 3:
            values = tuple(int(value) for value in digits[:3])
            return values in {
                (expected.year, expected.month, expected.day),
                (expected.month, expected.day, expected.year),
            }
        return False
    match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", raw)
    return bool(match and (int(match.group(1)), int(match.group(2))) == (expected.hour, expected.minute))


def _widget_button(field: WebElement, pattern: str) -> WebElement | None:
    """입력란과 같은 MUI 컨테이너에 있는 달력/시계 버튼을 찾는다."""
    for xpath in (
        "./following-sibling::button",
        "./parent::*//button",
    ):
        for button in field.find_elements(By.XPATH, xpath):
            name = " ".join(
                filter(None, (button.get_attribute("aria-label"), button.get_attribute("title"), button.text))
            )
            if re.search(pattern, name, re.I):
                return button
    return None


def _picker_month(driver: WebDriver) -> tuple[int, int] | None:
    # Headless Chrome에서는 팝업 애니메이션 직후 is_displayed()가 잠시 False를
    # 반환할 수 있으므로, 달력 헤더는 렌더링·텍스트 존재 여부로 판정한다.
    labels = [
        item
        for item in driver.find_elements(
            By.CSS_SELECTOR,
            ".MuiPickersCalendarHeader-label,[class*='PickersCalendarHeader-label']",
        )
        if item.text.strip()
    ]
    if not labels:
        return None
    text = labels[-1].text.strip()
    korean = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월", text)
    if korean:
        return int(korean.group(1)), int(korean.group(2))
    for fmt in ("%B %Y", "%b %Y", "%Y %B", "%Y %b"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.year, parsed.month
        except ValueError:
            pass
    return None


def _pick_widget_date(driver: WebDriver, field: WebElement, expected: datetime) -> bool:
    """키 입력이 무시되는 MUI 날짜 입력을 실제 달력 조작으로 보완한다."""
    button = _widget_button(field, r"날짜|date|calendar")
    if button is None:
        return False
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
    ActionChains(driver).move_to_element(button).click().perform()
    target = (expected.year, expected.month)
    try:
        current = WebDriverWait(driver, _SHORT_WAIT).until(lambda d: _picker_month(d))
        for _ in range(24):
            if current == target:
                break
            direction = 1 if current < target else -1
            pattern = r"다음\s*달|next\s*month" if direction > 0 else r"이전\s*달|previous\s*month"
            controls = [
                item
                for item in driver.find_elements(By.CSS_SELECTOR, "button")
                if re.search(pattern, item.get_attribute("aria-label") or item.get_attribute("title") or "", re.I)
            ]
            if not controls:
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                return False
            previous = current
            ActionChains(driver).move_to_element(controls[-1]).click().perform()
            current = WebDriverWait(driver, _SHORT_WAIT).until(
                lambda d: (value := _picker_month(d)) and value != previous and value
            )
        if current != target:
            return False
        days = [
            item
            for item in driver.find_elements(
                By.CSS_SELECTOR,
                "button.MuiPickersDay-root[role='gridcell'],button[role='gridcell']",
            )
            if item.text.strip() == str(expected.day)
            and "MuiPickersDay-dayOutsideMonth" not in (item.get_attribute("class") or "")
            and item.is_enabled()
        ]
        if not days:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            return False
        ActionChains(driver).move_to_element(days[-1]).click().perform()
        WebDriverWait(driver, _SHORT_WAIT).until(
            lambda _: _input_value_matches(field, expected, date_only=True)
        )
        return True
    except (StaleElementReferenceException, TimeoutException):
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        return False


def _set_widget_value(
    driver: WebDriver,
    field: WebElement,
    value: str,
    expected: datetime,
    *,
    date_only: bool,
) -> None:
    """날짜 선택기와 직접 입력을 조합해 MUI 제어 값을 반영한다."""
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", field)
    # 날짜는 실제 사용자가 조작하는 선택기를 우선 사용한다.
    # React 제어 input에 문자열만 주입하면 로컬에서는 반영돼도 Linux CI에서
    # 내부 상태가 이전 값으로 되돌아가는 경우가 있기 때문이다.
    if date_only and _pick_widget_date(driver, field, expected):
        return
    try:
        if field.get_attribute("readonly") is not None:
            raise ElementNotInteractableException("readonly widget")
        field.click()
        field.send_keys(Keys.CONTROL, "a")
        field.send_keys(Keys.BACKSPACE)
        field.send_keys(value)
        field.send_keys(Keys.TAB)
    except ElementNotInteractableException:
        _native(driver, field, value)

    try:
        WebDriverWait(driver, 1).until(
            lambda _: _input_value_matches(field, expected, date_only=date_only)
        )
        return
    except TimeoutException:
        # send_keys가 예외 없이 끝나도 React/MUI 상태가 갱신되지 않는 경우가 있다.
        _native(driver, field, value)
        driver.execute_script(
            "arguments[0].dispatchEvent(new FocusEvent('blur',{bubbles:true}));",
            field,
        )

    try:
        WebDriverWait(driver, 1).until(
            lambda _: _input_value_matches(field, expected, date_only=date_only)
        )
        return
    except TimeoutException:
        if date_only and _pick_widget_date(driver, field, expected):
            return

    WebDriverWait(driver, _SHORT_WAIT).until(
        lambda _: _input_value_matches(field, expected, date_only=date_only),
        message=f"일정 입력값 반영 실패: expected={value!r}, actual={field.get_attribute('value')!r}",
    )


def _schedule_times(driver: WebDriver, start: datetime, end: datetime, *, all_day: bool = False) -> None:
    """현재 일정 UI의 표시형 날짜 입력과 종일 토글을 함께 처리한다."""
    _schedule_option(driver, r"하루\s*종일|종일|all.day", all_day)
    # A comma-separated container selector cannot safely be suffixed once
    # (``A,B,C input`` also returns A and B themselves).  Spell out each
    # descendant selector so only real form inputs are considered.
    inputs = _visible(
        driver,
        By.CSS_SELECTOR,
        "[role='dialog'] input,.MuiPopover-paper input,.MuiDialog-paper input",
    )
    explicit_date_fields = [field for field in inputs if _widget_button(field, r"날짜|date|calendar")]
    date_fields = [
        field
        for field in inputs
        if field.get_attribute("type") in {"date", "datetime-local"}
        or re.search(r"date|calendar|시작|종료|yyyy|mm/dd", " ".join(
            field.get_attribute(name) or "" for name in ("name", "placeholder", "aria-label", "value")
        ), re.I)
    ]
    if len(explicit_date_fields) >= 2:
        date_fields = explicit_date_fields
    if len(date_fields) < 2:
        date_fields = [
            field
            for field in inputs
            if not re.search(
                r"summary|title|제목|course|과목|teacher|선생",
                " ".join(field.get_attribute(name) or "" for name in ("name", "placeholder", "aria-label")),
                re.I,
            )
        ][:2]
    assert len(date_fields) >= 2, f"일정 폼의 시작/종료 날짜 입력란을 찾지 못했습니다: {len(inputs)}개 입력란"
    # 이 서비스의 날짜 위젯은 type=date가 아닌 MM/DD/YYYY 표시형 text input을 쓴다.
    # 입력한 현지 달력 날짜를 그대로 사용한다. UTC 보정을 테스트에서 선반영하면
    # 실제 UI 선택일과 기대일이 달라져 날짜 경계 결함을 가릴 수 있다.
    for field, date_value in zip(date_fields[:2], (start, end)):
        input_type = (field.get_attribute("type") or "").lower()
        value = date_value.strftime("%Y-%m-%d" if input_type == "date" else "%m/%d/%Y")
        _set_widget_value(driver, field, value, date_value, date_only=True)
    if all_day:
        return
    time_fields = [
        field for field in inputs
        if field.get_attribute("type") == "time"
        or re.search(r"time|시간|hh:mm", " ".join(field.get_attribute(name) or "" for name in ("name", "placeholder", "aria-label")), re.I)
    ]
    explicit_time_fields = [field for field in inputs if _widget_button(field, r"시간|time|clock")]
    if len(explicit_time_fields) >= 2:
        time_fields = explicit_time_fields
    if len(time_fields) < 2 and len(inputs) >= 4:
        time_fields = [f for f in inputs if f not in date_fields[:2]][:2]
    time_fields = [field for field in time_fields if field.is_enabled()]
    if len(time_fields) >= 2:
        for field, time_value in zip(time_fields[:2], (start, end)):
            _set_widget_value(
                driver,
                field,
                time_value.strftime("%H:%M"),
                time_value,
                date_only=False,
            )


def _schedule_description(driver: WebDriver, value: str) -> str:
    fields = _visible(driver, By.CSS_SELECTOR, "[role='dialog'] textarea,.MuiPopover-paper textarea,.MuiDialog-paper textarea,[role='dialog'] [contenteditable=true],.MuiPopover-paper [contenteditable=true],.MuiDialog-paper [contenteditable=true]")
    assert fields
    original = fields[0].get_attribute("value") or fields[0].text or ""
    _set_text(fields[0], value)
    return original


def _schedule_option(driver: WebDriver, pattern: str, selected: bool) -> None:
    def matching_labels(d):
        return [label for label in _visible(d, By.TAG_NAME, "label") if re.search(pattern, label.text, re.I)] or False

    try:
        labels = WebDriverWait(driver, _SHORT_WAIT).until(matching_labels)
    except TimeoutException:
        labels = []
    if labels:
        control = labels[0].find_element(By.CSS_SELECTOR, "input[type='checkbox'],input[type='radio']")
        if control.is_selected() != selected:
            driver.execute_script("arguments[0].click();", control)
        assert control.is_selected() == selected
        return

    # This deployment exposes recurrence as the "반복없음" select rather
    # than a labelled checkbox.  Choose a concrete recurrence option through
    # the same UI a user sees.
    controls = [
        element
        for element in _visible(driver, By.CSS_SELECTOR, "button,[role='button'],[role='combobox']")
        if re.search(pattern, accessible_name(element), re.I)
    ]
    if not controls:
        texts = [element for element in text_elements(driver, re.compile(pattern, re.I), exact=False) if element.is_displayed()]
        for element in texts:
            candidate = driver.execute_script(
                "return arguments[0].closest('label,[role=switch],[role=checkbox],button') || arguments[0].parentElement;",
                element,
            )
            nested = candidate.find_elements(By.CSS_SELECTOR, "input[type='checkbox'],input[type='radio']") if candidate is not None else []
            if nested:
                control = nested[0]
                if control.is_selected() != selected:
                    driver.execute_script("arguments[0].click();", control)
                assert control.is_selected() == selected
                return
    assert controls, f"일정 옵션 /{pattern}/이 없습니다."
    click_when_ready(driver, controls[-1])
    choice_pattern = r"매일|매주|매달|매년" if selected else r"반복\s*없|반복\s*안"
    choices = WebDriverWait(driver, _SHORT_WAIT).until(
        lambda _: [element for element in text_elements(driver, re.compile(choice_pattern, re.I), exact=False) if element.is_displayed()]
    )
    click_when_ready(driver, _ancestor(driver, min(choices, key=lambda element: len(element.text))))


def _period(driver: WebDriver) -> str:
    labels = []
    for _ in range(10):
        labels = [e.text.strip() for e in _visible(driver, By.CSS_SELECTOR, ".fc-toolbar-title,[class*='toolbar-title'],[class*='calendar-title'],h2") if re.search(r"\d|월|주", e.text)]
        if not labels:
            labels = [
                e.text.strip()
                for e in _visible(driver, By.XPATH, "//*[contains(normalize-space(.), '년') and contains(normalize-space(.), '월')]")
                if re.fullmatch(r"\d{4}년\s*\d{1,2}월", e.text.strip())
            ]
        if not labels:
            for e in _visible(driver, By.XPATH, "//*[contains(normalize-space(.), '년') and contains(normalize-space(.), '월')]"):
                match = re.search(r"\d{4}년\s*\d{1,2}월", e.text)
                if match:
                    labels.append(match.group(0))
        if not labels:
            match = re.search(r"\d{4}년\s*\d{1,2}월", _body(driver))
            if match:
                labels.append(match.group(0))
        if labels:
            break
        time.sleep(0.5)
    assert labels, "캘린더 기간 라벨을 찾지 못했습니다."
    month = min(labels, key=len)
    # The schedule defaults to a week view.  Its month label stays unchanged
    # when moving between weeks in the same month, so include the rendered
    # weekday headers in the period identity.
    try:
        WebDriverWait(driver, 8).until(
            lambda d: len(_visible(d, By.CSS_SELECTOR, "[data-date],thead th,[role='columnheader']")) >= 5
        )
    except TimeoutException:
        pass
    dates = sorted({
        element.get_attribute("data-date")
        for element in _visible(driver, By.CSS_SELECTOR, "[data-date]")
        if element.get_attribute("data-date") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", element.get_attribute("data-date"))
    })
    if dates:
        return month + " | " + " | ".join(dates)
    weekdays = [
        header.text.strip()
        for header in _visible(driver, By.CSS_SELECTOR, "thead th,[role='columnheader']")
        if re.fullmatch(r"\d{1,2}일\s*\([일월화수목금토]\)", header.text.strip())
    ]
    return month + (" | " + " | ".join(weekdays) if weekdays else "")


def _schedule_move_period(driver: WebDriver, *, forward: bool) -> None:
    """Move the current schedule period using the icon-only toolbar controls."""
    today = next(
        (button for button in _visible(driver, By.CSS_SELECTOR, "button") if accessible_name(button) in {"오늘", "Today"}),
        None,
    )
    assert today is not None, "일정 도구막대의 오늘 버튼을 찾지 못했습니다."
    before = _period(driver)
    direction = "right" if forward else "left"
    selectors = (
        f"button[aria-label*='{direction}' i],button[aria-label*='{'다음' if forward else '이전'}'],"
        f"button:has(svg[data-testid*='chevron' i][data-testid*='{direction}' i])"
    )
    candidates = _visible(driver, By.CSS_SELECTOR, selectors)
    today_rect = today.rect
    candidates = [
        button for button in candidates
        if abs((button.rect["y"] + button.rect["height"] / 2) - (today_rect["y"] + today_rect["height"] / 2)) < 20
    ]
    if not candidates:
        candidates = [
            button for button in _visible(driver, By.CSS_SELECTOR, "button")
            if button.rect["x"] > today_rect["x"] + today_rect["width"] - 2
            and abs((button.rect["y"] + button.rect["height"] / 2) - (today_rect["y"] + today_rect["height"] / 2)) < 20
            and button.find_elements(By.CSS_SELECTOR, "svg")
        ]
        candidates.sort(key=lambda button: button.rect["x"])
        if candidates:
            candidates = [candidates[1 if forward and len(candidates) > 1 else 0]]
    assert candidates, "일정 이전/다음 아이콘 버튼을 찾지 못했습니다."
    click_when_ready(driver, candidates[0])
    WebDriverWait(driver, _SHORT_WAIT).until(lambda _: _period(driver) != before)


def _switch_schedule_list(driver: WebDriver) -> None:
    """Use the rightmost icon-only calendar/list toolbar control."""
    candidates = []
    for button in _visible(driver, By.CSS_SELECTOR, "main button"):
        try:
            if button.find_elements(By.CSS_SELECTOR, "svg") and button.rect["y"] < 220 and not button.text.strip():
                candidates.append(button)
        except StaleElementReferenceException:
            continue
    assert len(candidates) >= 2, "일정 목록 보기 아이콘 버튼을 찾지 못했습니다."
    # 프로필 등 전역 헤더 버튼을 제외한 main 내부 우측 보기 토글 중 오른쪽이 목록이다.
    target_x = max(button.rect["x"] for button in candidates)
    click_when_ready(
        driver,
        lambda: next(
            button for button in _visible(driver, By.CSS_SELECTOR, "main button")
            if abs(button.rect["x"] - target_x) < 2 and button.find_elements(By.CSS_SELECTOR, "svg") and not button.text.strip()
        ),
    )


def _cards(page: ClassSchedulePage) -> tuple[str, ...]:
    # Calendar cards have nested elements which match the broad Page Object
    # selector as well.  Keep one rendered item per visible text rather than
    # treating a card and its children as duplicate schedules.
    return tuple(dict.fromkeys(card.text.strip() for card in page.get_schedule_cards() if card.text.strip()))


def _stable_schedule_cards(page: ClassSchedulePage) -> tuple[str, ...]:
    """Return non-temporary cards for navigation/state-preservation checks."""
    return tuple(title for title in _cards(page) if not title.startswith(_QA_PREFIX))


def _stable_schedule_snapshot(
    data: IntegrationData,
    classroom_id: str,
    *,
    educator: bool = False,
) -> tuple[tuple[object, object, object, object], ...]:
    """Return an order-independent snapshot of persistent, non-QA schedules."""
    rows = (
        (item.get("id"), item.get("summary"), item.get("dt_start"), item.get("dt_end"))
        for item in _schedule_list(data, classroom_id, educator=educator)
        if not str(item.get("summary") or "").startswith(_QA_PREFIX)
    )
    return tuple(sorted(rows, key=lambda row: tuple(str(value or "") for value in row)))


def _today(driver: WebDriver) -> bool:
    return bool(_visible(driver, By.CSS_SELECTOR, ".fc-day-today,[aria-current=date],[class*='today'][class*='selected'],[data-today=true]"))


def _article_id(driver: WebDriver) -> int:
    match = re.search(r"/articles/(\d+)", urlparse(driver.current_url).path)
    assert match, f"게시글 URL에서 ID를 찾지 못했습니다: {driver.current_url}"
    return int(match.group(1))


def _article_detail(data: IntegrationData, article_id: int, *, educator: bool = False) -> dict:
    return _ok(api_client.get(article_get_url(data.api_base_url, data.org_name_short), headers=_headers(data, educator=educator), params={"board_article_id": article_id}))["board_article"]


def _author_name(article: dict) -> str:
    author = article.get("author")
    nested = author if isinstance(author, dict) else {}
    return str(article.get("author_name") or nested.get("fullname") or nested.get("name") or author or "").strip()


def _delete_article(data: IntegrationData, article_id: int) -> None:
    current = api_client.get(article_get_url(data.api_base_url, data.org_name_short), headers=_headers(data, educator=True), params={"board_article_id": article_id})
    if current.status_code in {400, 403, 404}:
        return
    current_body = current.json()
    if current.status_code == 200 and current_body.get("_result", {}).get("status") == "fail":
        return
    _ok(current)
    template = os.getenv("LXP_BOARD_ARTICLE_DELETE_PATH", "/org/{org}/board/article/delete/").strip()
    path = template.format(org=quote(data.org_name_short, safe=""))
    _ok(api_client.post(f"{data.api_base_url}/{path.lstrip('/')}", headers=_headers(data, educator=True), files=multipart({"board_article_id": article_id}), confirmed=True))
    verify = api_client.get(article_get_url(data.api_base_url, data.org_name_short), headers=_headers(data, educator=True), params={"board_article_id": article_id})
    assert verify.status_code in {200, 400, 404}
    if verify.status_code == 200:
        body = verify.json(); assert body.get("_result", {}).get("status") == "fail" and "board_article" not in body


def _article_rows(driver: WebDriver) -> list[WebElement]:
    rows = _visible(driver, By.CSS_SELECTOR, "table tbody tr")
    candidates = rows or _visible(driver, By.CSS_SELECTOR, "main [data-testid*='article'],main [class*='article-item'],main [class*='post-item']")
    # 전역 레이아웃의 메뉴 행을 게시글 검색 결과로 오인하지 않는다. 실제 게시글
    # 행은 상세 URL 링크·article ID·게시글 데이터 속성 중 하나를 가진다.
    article_rows = []
    for row in candidates:
        # 현재 게시판은 제목 링크나 article/post 클래스 없이 일반 table 행으로 렌더링한다.
        # td가 있는 행만 허용하면 전역 레이아웃의 탐색 메뉴 행은 제외하면서 실제 글 행은 보존한다.
        if row.tag_name.lower() == "tr" and row.find_elements(By.CSS_SELECTOR, "td"):
            row_text = row.text.strip()
            # Search-empty rows use the same table markup as a result row, but
            # do not represent an article and must not invalidate delete/search
            # assertions.
            if not re.search(r"등록된\s*게시글이\s*없|검색\s*결과가\s*없|게시글이\s*없", row_text):
                article_rows.append(row)
            continue
        links = row.find_elements(By.CSS_SELECTOR, "a[href*='/articles/']")
        marker = " ".join((row.get_attribute(name) or "") for name in ("data-testid", "data-article-id", "class"))
        if links or re.search(r"article|post|board", marker, re.I):
            article_rows.append(row)
    return article_rows


def _row_title(row: WebElement) -> str:
    cells = row.find_elements(By.TAG_NAME, "td")
    return (cells[0].text if cells else row.text).strip().splitlines()[0]


def _stable_board_titles(driver: WebDriver) -> tuple[str, ...]:
    """Return persistent board titles, excluding temporary automation records."""
    return tuple(
        title
        for title in (_row_title(row) for row in _article_rows(driver))
        if title and not title.startswith(_QA_PREFIX)
    )


def _comment_rows(driver: WebDriver) -> list[WebElement]:
    import time
    try:
        WebDriverWait(driver, 5).until(
            lambda d: bool(d.find_elements(By.XPATH, "//main//*[contains(text(), 'comment-') or contains(text(), 'qa6_')]"))
        )
    except Exception:
        pass

    # 1. 기존 특정 클래스 탐색
    rows = _visible(driver, By.CSS_SELECTOR, "main [class*='comment-item'],main [data-testid*='comment'],main [class*='CommentItem']")
    if rows:
        return rows

    # 2. 댓글 본문([QA-AUTO] 또는 comment-) 요소를 기준으로 상위 댓글 카드 컨테이너 탐색
    comment_texts = driver.find_elements(By.XPATH, "//main//*[contains(text(), 'comment-')]")
    containers = []
    for ct in comment_texts:
        try:
            if ct.is_displayed():
                container = driver.execute_script("""
                    let el = arguments[0];
                    while (el && el.parentElement && el.parentElement.tagName.toLowerCase() !== 'main') {
                        if (el.querySelector("button, [role='button']") && (el.innerText.includes('qa6_') || el.innerText.includes('전') || el.innerText.includes('좋아요'))) {
                            return el;
                        }
                        el = el.parentElement;
                    }
                    return arguments[0].parentElement;
                """, ct)
                if container and container not in containers:
                    containers.append(container)
        except Exception:
            continue
    if containers:
        return containers

    # 3. fallback: comment 클래스 포함 요소 중 본문이 있는 요소
    candidates = driver.find_elements(By.XPATH, "//main//*[contains(@class, 'comment') or contains(@class, 'Comment')]")
    valid_candidates = []
    for c in candidates:
        try:
            if c.is_displayed() and len(c.text.strip()) > 5:
                valid_candidates.append(c)
        except Exception:
            continue
    return valid_candidates


def _search(board: BoardPage, query: str, expected: str) -> tuple[str, ...]:
    board.search(query)
    WebDriverWait(board.driver, _SHORT_WAIT).until(lambda _: bool(_article_rows(board.driver)))
    titles = tuple(_row_title(row) for row in _article_rows(board.driver)); normalized = query.strip().casefold()
    assert titles and expected in titles and all(normalized in title.casefold() for title in titles)
    return titles


def _return_board_list(board: BoardPage) -> None:
    """상세 DOM이 전환 중일 때도 안정적으로 게시판 목록으로 복귀한다."""
    for _ in range(3):
        for button in board.driver.find_elements(By.CSS_SELECTOR, "button"):
            try:
                if re.search(r"목록|뒤로|back|list", accessible_name(button), re.I) and button.is_displayed():
                    board.driver.execute_script("arguments[0].click()", button)
                    board.expect_loaded()
                    return
            except StaleElementReferenceException:
                continue
    raise AssertionError("게시글 상세의 목록 복귀 버튼을 안정적으로 클릭하지 못했습니다.")


def _errors(driver: WebDriver) -> str:
    return "\n".join(e.text.strip() for e in _visible(driver, By.CSS_SELECTOR, ".Mui-error,[role=alert],[class*='error'],[class*='helper-text']") if e.text.strip())


def _focus_activate(driver: WebDriver, target: WebElement) -> WebElement:
    body = driver.find_element(By.TAG_NAME, "body"); driver.execute_script("arguments[0].focus();", body)
    for _ in range(100):
        body.send_keys(Keys.TAB); active = driver.switch_to.active_element
        if driver.execute_script("return arguments[0]===arguments[1]||arguments[0].contains(arguments[1]);", target, active):
            active.send_keys(Keys.ENTER); return active
    raise AssertionError("Tab 키로 대상 요소에 도달하지 못했습니다.")


def _focus_returned(driver: WebDriver, origin: WebElement) -> None:
    try:
        WebDriverWait(driver, _SHORT_WAIT).until(
            lambda d: d.execute_script(
                "return arguments[0]===document.activeElement||arguments[0].contains(document.activeElement);",
                origin,
            )
        )
    except TimeoutException as error:
        active = driver.switch_to.active_element
        raise AssertionError(
            f"상세를 닫은 뒤 일정 카드로 초점이 복귀하지 않았습니다: active={active.tag_name}"
        ) from error


def _tab_text(detail: CourseDetailPage, name: str) -> str:
    detail.select_tab(name); assert detail.selected_tab_name() == name
    panels = _visible(detail.driver, By.CSS_SELECTOR, "[role=tabpanel]")
    assert len(panels) == 1 and panels[0].text.strip()
    return panels[0].text.strip()


def _map(detail: CourseDetailPage) -> dict[str, str]:
    try:
        if detail.selected_tab_name() != detail.MAP_TAB:
            detail.select_tab(detail.MAP_TAB)
    except Exception:
        detail.select_tab(detail.MAP_TAB)

    selector = "[data-testid^='rf__node-'],.react-flow__node"

    def snapshot(driver: WebDriver) -> dict[str, str] | bool:
        result: dict[str, str] = {}
        for index, node in enumerate(_visible(driver, By.CSS_SELECTOR, selector)):
            try:
                text = node.text.strip()
                key = node.get_attribute("data-testid") or (text.splitlines()[0] if text else f"node-{index}")
                result[key] = "|".join((text, node.get_attribute("class") or "", node.get_attribute("aria-label") or ""))
            except StaleElementReferenceException:
                return False
        return result or False

    try:
        return WebDriverWait(detail.driver, _WAIT).until(snapshot)
    except TimeoutException:
        return {}


def _legacy(data: IntegrationData) -> LegacyCourseApi:
    return LegacyCourseApi(data.api_base_url, data.org_name_short)


def _responses(data: IntegrationData) -> list[dict]:
    try:
        res = _legacy(data).list_material_quiz_responses(data.material_quiz_id, data.learner_user_id, _headers(data), count=20, include_answer=True)
        if isinstance(res, dict) and res.get("_result", {}).get("status") == "ok":
            return res.get("quiz_responses", [])
    except Exception:
        pass
    return []


def _admissions(data: IntegrationData) -> list[dict]:
    try:
        res = _legacy(data).list_test_admissions(data.learner_user_id, data.lecture_id, _headers(data), count=20)
        if isinstance(res, dict) and res.get("_result", {}).get("status") == "ok":
            return res.get("test_admissions", [])
    except Exception:
        pass
    return []


def _cleanup_attempt(data: IntegrationData, original_ids: set[int]) -> None:
    try:
        for item in _responses(data):
            response_id = item.get("id")
            if isinstance(response_id, int) and response_id not in original_ids:
                try:
                    _ok(_legacy(data).delete_material_quiz_response(response_id, _headers(data), path=data.quiz_response_delete_path, confirmed=True))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        _ok(_legacy(data).reset_test_by_self(data.lecture_id, _headers(data), confirmed=True))
    except Exception:
        pass


def _login_required(driver: WebDriver, settings: E2ESettings, url: str, protected: str) -> None:
    driver.get(url); LoginPage(driver, settings).expect_login_required()
    public_text = driver.find_element(By.TAG_NAME, "body").text
    assert protected not in public_text


def _current_home(app: AppShell) -> ClassroomHomePage:
    home = ClassroomHomePage(app)
    home.open()
    home.expect_all_menus_visible()
    home.expect_all_widgets_visible()
    return home


def _active_menu(app: AppShell, name: str) -> None:
    home = ClassroomHomePage(app)
    home.expect_current_menu_highlighted(name)
    current = [
        e
        for e in role_elements(app.driver, "link", name)
        if e.is_displayed()
        and (
            e.get_attribute("aria-current") in {"page", "true"}
            or re.search(r"active|selected|current", e.get_attribute("class") or "", re.I)
        )
    ]
    assert len(current) == 1, f"{name!r} 현재 메뉴 표시가 정확히 하나가 아닙니다."


def _course_cards(page: CourseListPage) -> tuple[tuple[str, str], ...]:
    def find(_: WebDriver) -> list[WebElement]:
        return [
            element
            for element in role_elements(page.driver, "button")
            if element.is_displayed() and element.find_elements(By.TAG_NAME, "img")
        ]

    buttons = WebDriverWait(page.driver, _SHORT_WAIT).until(find)
    cards = []
    for button in buttons:
        lines = _lines(button.text)
        if lines:
            source = button.find_elements(By.TAG_NAME, "img")[0].get_attribute("src")
            # Course thumbnails use short-lived signed URLs.  The asset path,
            # not the regenerated query signature, is the stable UI value.
            cards.append((lines[0], source.split("?", 1)[0]))
    assert cards
    return tuple(cards)


def _lesson_panel(detail: CourseDetailPage, lesson: str) -> WebElement:
    leaf = detail.lesson_card(lesson)
    panels = leaf.find_elements(
        By.XPATH,
        "ancestor::*[.//button[contains(normalize-space(.),'테스트 시작') or contains(normalize-space(.),'학습 시작')]][1]",
    )
    return panels[0] if panels else leaf


def _iso_equal(actual: str, expected: datetime) -> bool:
    if not actual:
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(actual)):
        exp_date = expected.date() if isinstance(expected, datetime) else expected
        return str(actual) in (
            exp_date.isoformat(),
            (exp_date - timedelta(days=1)).isoformat(),
            (exp_date + timedelta(days=1)).isoformat(),
        )
    parsed = datetime.fromisoformat(str(actual).replace("Z", "+00:00"))
    if expected.tzinfo is None:
        return parsed.replace(tzinfo=None, second=0, microsecond=0) == expected.replace(second=0, microsecond=0)
    return parsed.astimezone(expected.tzinfo).replace(second=0, microsecond=0) == expected.replace(second=0, microsecond=0)


def _is_all_day_schedule(item: dict) -> bool:
    """API의 플래그형/날짜 전용형 종일 일정 표현을 동일하게 판별한다."""
    return bool(
        item.get("is_all_day")
        or item.get("all_day")
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(item.get("dt_start", "")))
    )


def _assert_schedule_exact(
    item: dict,
    *,
    title: str,
    start: datetime,
    end: datetime,
    description: str,
    all_day: bool = False,
) -> None:
    assert item.get("summary") == title
    is_all_day_item = _is_all_day_schedule(item)
    if all_day:
        assert is_all_day_item, item
        actual_start, actual_end = str(item.get("dt_start", "")), str(item.get("dt_end", ""))
        assert actual_start == start.date().isoformat(), item
        # The API currently represents a one-day all-day item with either an
        # inclusive same-day end or an exclusive next-day end.  Both describe
        # the exact UI day selected; no +/- one-day start-date tolerance is used.
        assert actual_end in {start.date().isoformat(), end.date().isoformat()}, item
    else:
        assert not is_all_day_item, item
        assert _iso_equal(item.get("dt_start", ""), start), item
        assert _iso_equal(item.get("dt_end", ""), end), item
    actual_description = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", item.get("description") or ""))).strip()
    assert actual_description == description


def _delete_schedules_by_title(data: IntegrationData, classroom_id: str, title: str) -> None:
    for _ in range(20):
        matches = _schedule_matches(data, classroom_id, title, educator=True)
        if not matches:
            return
        schedule_id = matches[0].get("id")
        assert isinstance(schedule_id, (int, str)) and str(schedule_id)
        _delete_schedule(data, classroom_id, schedule_id)
    assert not _schedule_matches(data, classroom_id, title, educator=True), f"반복 일정 정리가 완료되지 않았습니다: {title}"


def _create_schedule(
    page: ClassSchedulePage,
    data: IntegrationData,
    classroom_id: str,
    *,
    title: str,
    start: datetime,
    end: datetime,
    description: str = "",
    all_day: bool = False,
) -> dict:
    before = {item.get("id") for item in _schedule_list(data, classroom_id, educator=True)}
    page.open()
    page.click_create_schedule_button()
    page.fill_schedule_form(title=title)
    if description:
        _schedule_description(page.driver, description)
    _schedule_times(page.driver, start, end, all_day=all_day)
    page.submit_schedule_form()
    matches = [item for item in _schedule_matches(data, classroom_id, title, educator=True) if item.get("id") not in before]
    assert len(matches) == 1, f"{title!r} 일정이 정확히 하나 생성되지 않았습니다: {matches}"
    _assert_schedule_exact(
        matches[0], title=title, start=start, end=end,
        description=description, all_day=all_day,
    )
    return matches[0]


def _open_article(board: BoardPage, title: str) -> int:
    board.open()
    board.search(title)
    matches = [row for row in _article_rows(board.driver) if _row_title(row) == title]
    assert len(matches) == 1, f"{title!r} 게시글이 정확히 하나가 아닙니다."
    board.click_article(title)
    assert board.get_detail_title() == title
    return _article_id(board.driver)


def _create_article(
    board: BoardPage,
    *,
    title: str,
    content: str,
    attachment: Path | None = None,
    secret: bool = False,
) -> int:
    for attempt in range(2):
        try:
            board.open()
            board.click_write_button()
            break
        except StaleElementReferenceException:
            if attempt:
                raise
            board = BoardPage(board.app)
            time.sleep(0.5)
    board.fill_article_form(
        title=title,
        content=content,
        attachment_path=str(attachment) if attachment else None,
        is_secret=secret,
    )
    board.submit_article_form()
    if not re.search(r"/articles/\d+", board.driver.current_url):
        return _open_article(board, title)
    try:
        WebDriverWait(board.driver, _SHORT_WAIT).until(lambda d: title in _body(d))
    except TimeoutException:
        board.driver.refresh()
        WebDriverWait(board.driver, _SHORT_WAIT).until(lambda d: title in _body(d))
    headings = [
        element for element in _visible(board.driver, By.CSS_SELECTOR, "main h1,main h2,main h3,main h4,[role='heading']")
        if element.text.strip() == title
    ]
    assert len(headings) == 1, f"게시글 상세 제목이 일치하지 않습니다: {title!r}"
    return _article_id(board.driver)


def _sort_titles(board: BoardPage, *, latest: bool) -> tuple[str, ...]:
    board.open()
    (board.sort_by_latest if latest else board.sort_by_oldest)()
    WebDriverWait(board.driver, _SHORT_WAIT).until(lambda _: bool(_article_rows(board.driver)))
    return tuple(_row_title(row) for row in _article_rows(board.driver))


def _form_input(driver: WebDriver, selector: str) -> WebElement:
    def find(_: WebDriver) -> list[WebElement]:
        fields = _visible(driver, By.CSS_SELECTOR, selector)
        # The board editor's title field has only the visible "제목" label in
        # this deployment (no stable name/placeholder).  Limit the fallback to
        # an input in the editor area so the global header search is never used.
        if not fields and ("name='title'" in selector or "placeholder*='제목'" in selector):
            fields = [
                field
                for field in _visible(driver, By.CSS_SELECTOR, "main input:not([type='hidden']), form input:not([type='hidden'])")
                if not driver.execute_script(
                    "return arguments[0].closest('header, nav, [role=dialog]') !== null;", field
                )
            ]
        return fields

    fields = WebDriverWait(driver, _SHORT_WAIT).until(find)
    assert fields, f"입력 필드를 찾지 못했습니다: {selector}"
    return fields[0]


def _assert_no_blank_optional_section(driver: WebDriver) -> None:
    optional = _visible(driver, By.CSS_SELECTOR, "[data-testid*='linked-course'],[data-testid*='attachment'],[class*='attachment'],[class*='linked-course']")
    for section in optional:
        if not section.text.strip() and not section.find_elements(By.CSS_SELECTOR, "a,img,button"):
            assert section.rect["height"] <= 48, f"비어 있는 선택 정보 영역이 과도하게 큽니다: {section.rect}"


def _article_action(board: BoardPage, pattern: str) -> None:
    more = [
        e
        for e in _visible(board.driver, By.CSS_SELECTOR, "button,[role='button']")
        if re.search(r"더보기|메뉴|more", accessible_name(e), re.I)
        or e.find_elements(By.CSS_SELECTOR, "svg[data-testid*='More'],svg[data-icon='ellipsis']")
    ]
    assert more, "게시글 더보기 메뉴를 찾지 못했습니다."
    click_when_ready(board.driver, more[-1])
    # The service labels these menu actions as e.g. "게시글 수정", while the
    # spreadsheet scenario uses the shorter "수정" action name.  Match the
    # visible menu control by either form instead of requiring the whole label.
    action_words = tuple(re.findall(r"[가-힣A-Za-z]+", pattern))
    choices = WebDriverWait(board.driver, _SHORT_WAIT).until(
        lambda _: [
            e
            for e in _visible(board.driver, By.CSS_SELECTOR, "button,[role='menuitem'],[role='button'],a")
            if any(word in accessible_name(e) for word in action_words)
        ]
    )
    assert choices, f"게시글 작업 /{pattern}/ 항목이 없습니다."
    click_when_ready(board.driver, _ancestor(board.driver, choices[-1]))


def _like_button(driver: WebDriver) -> WebElement:
    def safe_label(element: WebElement) -> str:
        try:
            return accessible_name(element) + " " + element.text
        except StaleElementReferenceException:
            return ""

    # 1. '게시물 좋아요' 텍스트 포함 버튼 우선
    article_likes = [
        e for e in _visible(driver, By.CSS_SELECTOR, "button,[role='button']")
        if re.search(r"게시물\s*좋아요|본문\s*좋아요", safe_label(e), re.I)
    ]
    if article_likes:
        return article_likes[0]

    # 2. 댓글 영역(comment) 밖의 좋아요 버튼
    controls = [
        e for e in _visible(driver, By.CSS_SELECTOR, "button,[role='button']")
        if re.search(r"좋아요|추천|like", safe_label(e), re.I)
        and not driver.execute_script("return arguments[0].closest('[class*=\"comment\"], [class*=\"Comment\"]') !== null;", e)
    ]
    if controls:
        return controls[-1]

    # 3. fallback
    all_controls = [
        e for e in _visible(driver, By.CSS_SELECTOR, "button,[role='button']")
        if re.search(r"좋아요|추천|like", safe_label(e), re.I)
    ]
    assert all_controls, "게시글 좋아요 버튼을 찾지 못했습니다."
    return all_controls[0]


def _like_state(button: WebElement) -> tuple[bool, int]:
    parent_text = button.find_element(By.XPATH, "..").text
    text = " ".join((accessible_name(button), button.text, parent_text, button.get_attribute("class") or ""))
    selected = button.get_attribute("aria-pressed") == "true" or bool(re.search(r"selected|liked", text, re.I))
    numbers = re.findall(r"\d+", text)
    assert numbers, f"좋아요 수를 읽을 수 없습니다: {text!r}"
    return selected, int(numbers[-1])


def _select_educator_only(driver: WebDriver) -> None:
    time.sleep(0.5)
    labels = []
    for _ in range(5):
        labels = [
            e
            for e in text_elements(driver, re.compile(r"기관.*교육자|교육자.*전용|교육자.*공개|educator", re.I))
            if e.is_displayed()
        ]
        if not labels:
            labels = [
                e for e in driver.find_elements(By.XPATH, "//*[contains(text(), '교육자') or contains(text(), '기관')]")
                if e.is_displayed() and e.tag_name.lower() in ("label", "span", "p", "div", "button")
            ]
        if labels:
            break
        time.sleep(0.5)
    assert labels, "비밀글의 기관 교육자 공개 옵션을 찾지 못했습니다."
    target = driver.execute_script(
        "return arguments[0].closest('label,[role=radio],[role=option],button') || arguments[0];",
        labels[-1],
    )
    try:
        click_when_ready(driver, target)
    except Exception:
        driver.execute_script("arguments[0].click();", target)
    time.sleep(0.5)


def _restore_publication(app: AppShell, course: str, lesson: str, state: bool) -> None:
    management = CourseManagementPage(app)
    management.open()
    management.open_course(course)
    management.set_publication_state(lesson, state)
    management.expect_publication_state(lesson, state)

__all__ = [name for name in list(globals().keys()) if not name.startswith('__')]
