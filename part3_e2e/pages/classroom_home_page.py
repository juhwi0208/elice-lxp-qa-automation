"""
classroom_home_page.py
클래스 홈 화면 Page Object.

담당 기능:
  - 클래스 홈 진입 및 로드 확인
  - 좌측 메뉴(학습 과목·수업 일정·게시판) 선택
  - 위젯 제목·데이터 존재 확인
  - 클래스 전환 (여러 클래스 수강 시)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from part3_e2e.config import E2ESettings
from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.common.selenium_support import (
    click_when_ready,
    role_elements,
    text_elements,
    wait_role,
    wait_text,
    wait_url,
    wait_visible,
)

_LOAD_TIMEOUT = 20


@dataclass(frozen=True)
class WidgetSnapshot:
    """새로고침·전체 화면 이동 전후를 비교하기 위한 홈 위젯 기준값."""

    title: str
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class ClassroomHomePage:
    """클래스 홈 화면의 위젯·메뉴·클래스 전환을 담당한다."""

    # 위젯 제목 상수
    WIDGET_COURSE = "학습 과목"
    WIDGET_SCHEDULE = "수업 일정"
    WIDGET_BOARD = "게시판"

    # 통합 E2E가 사용하는 읽기 쉬운 별칭
    COURSE_WIDGET = WIDGET_COURSE
    SCHEDULE_WIDGET = WIDGET_SCHEDULE
    BOARD_WIDGET = WIDGET_BOARD
    WIDGET_TITLES = (COURSE_WIDGET, SCHEDULE_WIDGET, BOARD_WIDGET)
    LOAD_TIMEOUT = 30

    # 메뉴 이름 상수
    MENU_COURSE = "학습 과목"
    MENU_SCHEDULE = "수업 일정"
    MENU_BOARD = "게시판"

    def __init__(self, app: AppShell) -> None:
        self.app = app
        self.driver = app.driver
        self.settings = app.settings
        self.classroom = app.classroom

    # ──────────────────────────────────────────────
    # 화면 이동
    # ──────────────────────────────────────────────

    def open(self) -> None:
        """클래스 홈 화면으로 이동하고 로드를 기다린다."""
        self.app.open_classroom()
        self.wait_until_loaded()

    def wait_until_loaded(self) -> None:
        """클래스 홈 URL이 활성화될 때까지 대기한다."""
        from urllib.parse import urlparse
        expected_path = self.app.classroom_path.rstrip("/")
        WebDriverWait(self.driver, _LOAD_TIMEOUT).until(
            lambda d: urlparse(d.current_url).path.rstrip("/") == expected_path
        )


    def expect_loaded(self) -> None:
        """통합 시나리오용 클래스 홈 로드 검증."""
        self.wait_until_loaded()
        for title in self.WIDGET_TITLES:
            wait_text(self.driver, self.driver, title, timeout=self.LOAD_TIMEOUT)

    def reload(self) -> None:
        """클래스 홈 화면을 새로고침하고 다시 로드를 기다린다."""
        self.driver.refresh()
        self.wait_until_loaded()

    # ──────────────────────────────────────────────
    # 메뉴 탐색
    # ──────────────────────────────────────────────

    def ensure_sidebar_open(self) -> None:
        """좌측 사이드바가 닫혀있다면 상단 햄버거 메뉴(선 3개 아이콘)를 클릭해 펼친다."""
        self.app.ensure_sidebar_open()

    def get_menu_links(self) -> list[WebElement]:
        """좌측 사이드바에 있는 모든 메뉴 링크를 반환한다."""
        self.ensure_sidebar_open()
        return role_elements(self.driver, "link")

    def is_menu_visible(self, name: str) -> bool:
        """지정한 이름의 메뉴 링크가 화면에 표시되는지 확인한다."""
        try:
            wait_role(self.driver, self.driver, "link", name, timeout=3)
            return True
        except TimeoutException:
            pass

        # 사이드바가 닫혀있을 수 있으므로 햄버거 메뉴를 눌러 펼치고 재확인
        self.ensure_sidebar_open()
        try:
            wait_role(self.driver, self.driver, "link", name, timeout=5)
            return True
        except TimeoutException:
            from selenium.webdriver.common.by import By
            elements = self.driver.find_elements(
                By.XPATH,
                f"//a[contains(., '{name}')] | //button[contains(., '{name}')] | //*[contains(text(), '{name}')]",
            )
            return any(e.is_displayed() for e in elements)

    def select_menu(self, name: str) -> None:
        """지정한 이름의 좌측 메뉴를 클릭해 해당 화면으로 이동한다."""
        self.ensure_sidebar_open()
        self.app.select_menu(name)

    def expect_all_menus_visible(self) -> None:
        """클래스 홈에서 세 메뉴(학습 과목·수업 일정·게시판)가 모두 표시됨을 검증한다."""
        self.ensure_sidebar_open()
        for menu_name in (self.MENU_COURSE, self.MENU_SCHEDULE, self.MENU_BOARD):
            assert self.is_menu_visible(menu_name), (
                f"클래스 홈 좌측 메뉴 '{menu_name}'이 표시되지 않습니다."
            )

    def expect_current_menu_highlighted(self, name: str) -> None:
        """선택한 메뉴가 활성(aria-current 또는 active 클래스) 상태인지 확인한다."""
        self.ensure_sidebar_open()
        links = role_elements(self.driver, "link", name)
        visible = [l for l in links if l.is_displayed()]
        assert visible, f"'{name}' 메뉴 링크를 찾을 수 없습니다."
        # aria-current="page" 또는 class에 active/selected 포함 여부 확인
        link = visible[0]
        aria_current = link.get_attribute("aria-current") or ""
        class_attr = link.get_attribute("class") or ""
        assert (
            "page" in aria_current
            or "true" in aria_current
            or "active" in class_attr
            or "selected" in class_attr
            or "current" in class_attr
        ), (
            f"'{name}' 메뉴가 활성 상태로 표시되지 않습니다. "
            f"aria-current='{aria_current}', class='{class_attr}'"
        )

    # ──────────────────────────────────────────────
    # 위젯 확인
    # ──────────────────────────────────────────────

    def is_widget_visible(self, widget_title: str) -> bool:
        """지정한 제목의 위젯이 화면에 표시되는지 확인한다."""
        try:
            wait_text(self.driver, self.driver, widget_title, exact=False, timeout=10)
            return True
        except TimeoutException:
            return False

    def expect_all_widgets_visible(self) -> None:
        """세 위젯(학습 과목·수업 일정·게시판)이 겹치거나 깨지지 않고 표시됨을 검증한다."""
        for widget_title in (self.WIDGET_COURSE, self.WIDGET_SCHEDULE, self.WIDGET_BOARD):
            assert self.is_widget_visible(widget_title), (
                f"클래스 홈 '{widget_title}' 위젯이 표시되지 않습니다."
            )

    def _widget(self, title: str) -> WebElement:
        """사이드바가 아닌 클래스 홈의 최소 위젯 컨테이너를 찾는다."""
        wait_text(self.driver, self.driver, title, timeout=self.LOAD_TIMEOUT)
        candidates: list[WebElement] = []
        for title_element in text_elements(self.driver, title):
            if not title_element.is_displayed():
                continue
            candidates.extend(
                title_element.find_elements(
                    By.XPATH,
                    "ancestor::*[.//*[normalize-space()='전체 보기']][1]/parent::*",
                )
            )
        candidates = [
            candidate
            for candidate in candidates
            if "탐색" not in candidate.text and "내 클래스" not in candidate.text
        ]
        assert candidates, f"{title!r} 홈 위젯 영역을 찾지 못했습니다."
        return min(candidates, key=lambda element: len(element.text))

    @staticmethod
    def _normalized_lines(element: WebElement, title: str) -> tuple[str, ...]:
        ignored = {
            title,
            "전체 보기",
            "학습 시작하기",
            "QUIZ",
            "새 게시글 쓰기",
        }
        return tuple(
            line.strip()
            for line in element.text.splitlines()
            if line.strip() and line.strip() not in ignored
        )

    def snapshot(self, title: str) -> WidgetSnapshot:
        """특정 홈 위젯의 안정적인 표시 데이터를 캡처한다."""
        def capture(_driver) -> tuple[str, ...] | bool:
            try:
                lines = self._normalized_lines(self._widget(title), title)
                return lines or False
            except (AssertionError, StaleElementReferenceException):
                return False

        lines = WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            capture,
            message=f"{title!r} 홈 위젯의 기준 데이터를 찾지 못했습니다.",
        )
        return WidgetSnapshot(title=title, lines=tuple(lines))

    def get_first_widget_item_text(self, title: str) -> str:
        """위젯의 첫 번째 데이터(제목 등) 텍스트를 반환한다."""
        snap = self.snapshot(title)
        if snap and snap.lines:
            return snap.lines[0]
        return ""

    def snapshots(self) -> dict[str, WidgetSnapshot]:
        """학습 과목·수업 일정·게시판 위젯의 현재 기준값을 반환한다."""
        return {title: self.snapshot(title) for title in self.WIDGET_TITLES}

    def expect_snapshots(self, expected: dict[str, WidgetSnapshot]) -> None:
        """재진입 후 홈 위젯 데이터가 유지되는지 검증한다."""
        def check_matches(_driver) -> bool:
            try:
                actual = self.snapshots()
                return actual == expected
            except Exception:
                return False

        try:
            WebDriverWait(self.driver, 10).until(check_matches)
        except Exception:
            actual = self.snapshots()
            assert actual == expected, (
                "클래스 홈 새로고침·재진입 후 위젯 기준값이 달라졌습니다.\n"
                f"기대값: {expected}\n실제값: {actual}"
            )

    def expect_widget_contains(self, title: str, expected_text: str) -> None:
        """홈 위젯에 지정한 데이터가 표시되는지 검증한다."""
        snapshot = self.snapshot(title)
        assert expected_text in snapshot.text, (
            f"{title!r} 위젯에 {expected_text!r}가 표시되지 않았습니다. "
            f"실제 내용: {snapshot.lines}"
        )

    def get_course_widget_items(self) -> list[WebElement]:
        """학습 과목 위젯 안의 과목 카드 요소 목록을 반환한다."""
        widget_candidates = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '학습 과목') and "
            "not(.//*[contains(normalize-space(.), '학습 과목')])]"
        )
        if not widget_candidates:
            return []
        widget = widget_candidates[0]
        return widget.find_elements(By.CSS_SELECTOR, "[class*='card'], [class*='item'], li")

    def get_schedule_widget_items(self) -> list[WebElement]:
        """수업 일정 위젯 안의 일정 항목 요소 목록을 반환한다."""
        widget_candidates = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '수업 일정') and "
            "not(.//*[contains(normalize-space(.), '수업 일정')])]"
        )
        if not widget_candidates:
            return []
        widget = widget_candidates[0]
        return widget.find_elements(By.CSS_SELECTOR, "[class*='item'], li, [class*='schedule']")

    def get_board_widget_items(self) -> list[WebElement]:
        """게시판 위젯 안의 게시글 항목 요소 목록을 반환한다."""
        widget_candidates = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '게시판') and "
            "not(.//*[contains(normalize-space(.), '게시판')])]"
        )
        if not widget_candidates:
            return []
        widget = widget_candidates[0]
        return widget.find_elements(By.CSS_SELECTOR, "[class*='item'], li, [class*='post']")

    def click_view_all_courses(self) -> None:
        """학습 과목 위젯의 '전체 보기' 또는 '더 보기' 링크를 클릭한다."""
        self.app.open_classroom_section("courses")


    def click_view_all_schedules(self) -> None:
        """수업 일정 위젯의 '전체 보기' 링크를 클릭한다."""
        self.app.open_classroom_section("schedules")


    def click_view_all_board(self) -> None:
        """게시판 위젯의 '전체 보기' 링크를 클릭한다."""
        self.app.open_classroom_section("articles")


    # ──────────────────────────────────────────────
    # 클래스명 확인
    # ──────────────────────────────────────────────

    def get_current_class_name(self) -> str:
        """현재 선택된 클래스명을 헤더에서 읽어 반환한다."""
        try:
            heading = wait_role(self.driver, self.driver, "heading", timeout=5)
            return heading.text.strip()
        except Exception:
            return ""

    def expect_no_class_data_mix(self, expected_class_id: str) -> None:
        """현재 URL에 올바른 클래스 ID가 포함됐는지 확인한다."""
        assert expected_class_id in self.driver.current_url, (
            f"다른 클래스 데이터가 섞였습니다. 기대 클래스 ID: {expected_class_id}"
        )
