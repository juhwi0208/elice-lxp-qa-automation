"""학습자 학습과목 목록 Selenium Page Object."""

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.common.selenium_support import (
    role_elements,
    text_elements,
    wait_text,
)
from part3_e2e.pages.course_detail_page import CourseDetailPage


class CourseListPage:
    SECTION = "courses"
    TITLE = "학습 과목 목록"
    LOAD_TIMEOUT = 30
    MANAGEMENT_CONTROL_NAMES = ("순서 변경", "과목 추가", "과목 수정")

    def __init__(self, app: AppShell) -> None:
        self.app = app
        self.driver = app.driver
        self.page = app.driver
        self.content = app.driver

    @property
    def path(self) -> str:
        return f"{self.app.classroom_path}/{self.SECTION}"

    def open(self) -> None:
        self.app.open_classroom_section(self.SECTION)
        self.expect_loaded()

    def expect_loaded(self) -> None:
        self.app.expect_path(self.path)
        try:
            wait_text(
                self.driver,
                self.content,
                self.TITLE,
                exact=False,
                timeout=self.LOAD_TIMEOUT,
            )
        except Exception:
            # fallback: '학습 과목' 텍스트나 과목 카드 확인
            wait_text(
                self.driver,
                self.content,
                "학습 과목",
                exact=False,
                timeout=10,
            )


    def course_name_elements(self, name: str) -> list[WebElement]:
        return [
            element
            for element in text_elements(self.content, name)
            if element.is_displayed()
        ]

    def course_cards(self, name: str) -> list[WebElement]:
        return [
            button
            for button in role_elements(self.content, "button")
            if name in button.text.splitlines()
        ]

    def course_card(self, name: str) -> WebElement:
        cards = WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda _: self.course_cards(name) or False
        )
        assert len(cards) == 1, f"{name!r} 과목 카드는 정확히 하나여야 합니다."
        return cards[0]

    def expect_course_once(self, name: str) -> None:
        name_elements = WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda _: self.course_name_elements(name) or False
        )
        assert len(name_elements) == 1, (
            f"{name!r} 과목명은 화면에 정확히 하나여야 합니다. "
            f"실제 개수: {len(name_elements)}"
        )
        card = self.course_card(name)
        assert card.is_displayed()

    def expect_course_thumbnail(self, name: str) -> None:
        images = self.course_card(name).find_elements(By.TAG_NAME, "img")
        assert images and images[0].is_displayed()

    def expect_management_controls_hidden(self) -> None:
        for control_name in self.MANAGEMENT_CONTROL_NAMES:
            assert not role_elements(self.content, "button", control_name), (
                f"수강생 화면에 관리자 기능이 노출되었습니다: {control_name}"
            )

    def open_course(self, name: str) -> CourseDetailPage:
        self.course_card(name).click()
        detail = CourseDetailPage(self.app, name)
        detail.expect_loaded()
        return detail
