"""전체 기능 통합 시나리오용 수업 일정 Page Object."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.common.selenium_support import wait_text


class SchedulePage:
    MENU_NAME = "수업 일정"
    LOAD_TIMEOUT = 30
    MANAGEMENT_TEXTS = ("일정 만들기", "일정 추가", "새 일정")

    def __init__(self, app: AppShell) -> None:
        self.app = app
        self.driver = app.driver
        self.content = app.driver

    def open(self) -> None:
        self.app.select_menu(self.MENU_NAME)
        self.expect_loaded()

    def expect_loaded(self) -> None:
        wait_text(self.driver, self.content, self.MENU_NAME, timeout=self.LOAD_TIMEOUT)
        WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda driver: self.app.classroom.classroom_id in driver.current_url
        )

    def visible_text(self) -> str:
        body = self.driver.find_element(By.TAG_NAME, "body").text.strip()
        assert body, "수업 일정 화면의 본문이 비어 있습니다."
        return body

    def expect_home_data_visible(self, home_widget_text: str) -> None:
        candidates = [
            line for line in home_widget_text.splitlines()
            if len(line.strip()) >= 2 and line.strip() not in {"오늘"}
        ]
        assert candidates, "홈 일정 위젯에서 비교 가능한 기준값을 찾지 못했습니다."
        page_text = WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda driver: (
                text
                if any(candidate in text for candidate in candidates)
                else False
            )
            if (text := driver.find_element(By.TAG_NAME, "body").text.strip())
            else False,
            message="홈 일정 기준값이 전체 일정 화면에 로드되지 않았습니다.",
        )
        assert any(candidate in page_text for candidate in candidates), (
            "홈 일정 위젯과 전체 일정 화면에서 일치하는 날짜·제목을 찾지 못했습니다. "
            f"기준값: {candidates}\n전체 일정 화면: {page_text[:1200]}"
        )

    def expect_learner_management_hidden(self) -> None:
        page_text = self.visible_text()
        visible = [text for text in self.MANAGEMENT_TEXTS if text in page_text]
        assert not visible, f"수강생 일정 화면에 관리 기능이 노출됐습니다: {visible}"
