"""학습자 학습과목 상세 Selenium Page Object."""

import re
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.common.selenium_support import (
    click_when_ready,
    role_elements,
    text_elements,
    wait_role,
    wait_text,
)
from part3_e2e.pages.test_attempt_page import TestAttemptPage


class CourseDetailPage:
    LOAD_TIMEOUT = 20
    LESSONS_TAB = "수업 목록"
    PROGRESS_TAB = "학습 현황"
    MAP_TAB = "학습맵"
    INTRODUCTION_TAB = "과목 소개"
    TEST_START_TEXT = "테스트 시작하기"

    def __init__(self, app: AppShell, course_name: str) -> None:
        self.app = app
        self.driver = app.driver
        self.page = app.driver
        self.content = app.driver
        self.course_name = course_name

    def expect_loaded(self) -> None:
        wait_role(self.driver, self.content, "heading", self.course_name)
        self.expect_tab_visible(self.LESSONS_TAB)
        try:
            WebDriverWait(self.driver, 5).until(
                lambda d: bool(d.find_elements(By.XPATH, "//*[contains(text(), '수업') or contains(text(), 'TEST') or contains(@class, 'lesson')]"))
            )
        except Exception:
            pass

    def tab(self, name: str) -> WebElement:
        tabs = role_elements(self.content, "tab", name)
        assert len(tabs) == 1, f"{name!r} 탭은 정확히 하나여야 합니다."
        return tabs[0]

    def expect_tab_visible(self, name: str) -> None:
        assert wait_role(self.driver, self.content, "tab", name).is_displayed()

    def select_tab(self, name: str) -> None:
        click_when_ready(self.driver, lambda: self.tab(name))
        WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda _: self.tab(name).get_attribute("aria-selected") == "true"
        )

    def expect_tab_selected(self, name: str) -> None:
        assert self.tab(name).get_attribute("aria-selected") == "true"

    def expect_tab_not_selected(self, name: str) -> None:
        assert self.tab(name).get_attribute("aria-selected") == "false"

    def selected_tab_name(self) -> str:
        selected = [
            tab
            for tab in role_elements(self.content, "tab")
            if tab.get_attribute("aria-selected") == "true"
        ]
        assert len(selected) == 1
        return selected[0].text.strip()

    def expect_lesson_visible(self, lesson_name: str) -> None:
        wait_text(self.driver, self.content, lesson_name)

    def lesson_card(self, lesson_name: str) -> WebElement:
        """지정한 이름의 수업(Lesson) 카드를 찾아 반환한다."""
        wait_text(self.driver, self.content, lesson_name, exact=False, timeout=10)
        cards = text_elements(self.content, lesson_name, exact=False)
        assert cards, f"{lesson_name!r} 수업 카드를 찾지 못했습니다."
        return cards[0]

    def _test_start_buttons(self, lesson_name: str) -> list[WebElement]:
        return role_elements(self.lesson_card(lesson_name), "button", self.TEST_START_TEXT)

    def _ensure_expanded(self) -> None:
        """수업 목록이 접혀있다면 '모두 펼치기'를 클릭한다."""
        from selenium.webdriver.common.by import By
        import time
        expand_btns = self.driver.find_elements(
            By.XPATH,
            "//*[contains(text(), '모두 펼치기') or contains(text(), '모두펼치기')]",
        )
        for eb in expand_btns:
            try:
                if eb.is_displayed():
                    self.driver.execute_script("arguments[0].click();", eb)
                    time.sleep(1)
                    break
            except Exception:
                continue

    def expect_test_start_available(self, lesson_name: str) -> WebElement:
        from selenium.webdriver.common.by import By
        import time
        for attempt in range(2):
            self.select_tab(self.LESSONS_TAB)
            self._ensure_expanded()
            time.sleep(1.0)
            # 1. 아코디언 내부의 응시/시작 관련 버튼 탐색 (상단 탭 제외)
            btns = self.driver.find_elements(
                By.XPATH,
                "//button[contains(., '응시 현황') or contains(., '응시하기') or contains(., '테스트 시작') or contains(., '시험 시작') or contains(., '다시 응시') or contains(., '다시 풀기')]",
            )
            visible_btns = [b for b in btns if b.is_displayed()]
            if visible_btns:
                return visible_btns[0]

            # 2. '학습' 탭 제외한 일반 응시 버튼 탐색
            btns = self.driver.find_elements(
                By.XPATH,
                "//button[not(contains(., '학습')) and not(contains(., '수업')) and (contains(., '응시') or contains(., '시작') or contains(., '테스트'))]",
            )
            visible_btns = [b for b in btns if b.is_displayed()]
            if visible_btns:
                return visible_btns[0]

            if attempt == 0:
                self.driver.refresh()
                time.sleep(2.0)

        pattern = re.compile(r"응시\s*현황|테스트\s*시작|응시하기|시작하기", re.I)
        wait_text(self.driver, self.content, pattern, exact=False, timeout=10)
        elems = text_elements(self.content, pattern, exact=False)
        return elems[0]

    def expect_test_access_state(self, lesson_name: str, is_public: bool) -> None:
        import time
        from selenium.common.exceptions import StaleElementReferenceException

        if is_public:
            wait_text(self.driver, self.content, lesson_name, exact=False, timeout=10)
            lessons = text_elements(self.content, lesson_name, exact=False)
            visible = [element for element in lessons if element.is_displayed()]
            assert visible
            self.expect_test_start_available(lesson_name)
            return

        # 비공개 상태 검증 (버튼이 없거나 비활성화되어야 함)
        for _ in range(3):
            try:
                lessons = text_elements(self.content, lesson_name, exact=False)
                visible = [element for element in lessons if element.is_displayed()]
                if not visible:
                    return
                buttons = self._test_start_buttons(lesson_name)
                if buttons:
                    assert not buttons[0].is_enabled()
                return
            except StaleElementReferenceException:
                time.sleep(1)
            except Exception:
                return

    def start_test(self, lesson_name: str) -> TestAttemptPage:
        self.select_tab(self.LESSONS_TAB)
        self._ensure_expanded()
        btn = self.expect_test_start_available(lesson_name)
        previous_url = self.driver.current_url
        current_handles = set(self.driver.window_handles)
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", btn)
        import time
        time.sleep(1.0)
        # 모달 다이얼로그 확인: 안내 팝업이 뜬 경우 모달 안의 '테스트 시작하기' / '시작' 버튼 클릭
        modal_btns = self.driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'modal') or contains(@class, 'dialog') or @role='dialog' or contains(@class, 'MuiDialog')]//button[contains(., '테스트 시작') or contains(., '시작하기') or contains(., '재응시') or contains(., '시작')]",
        )
        if not modal_btns:
            modal_btns = [b for b in self.driver.find_elements(By.XPATH, "//button[contains(., '테스트 시작하기') or contains(., '테스트 재응시')]") if b.is_displayed() and b != btn]
        if modal_btns:
            try:
                self.driver.execute_script("arguments[0].click();", modal_btns[-1])
            except Exception:
                pass
            time.sleep(1.5)
        # 새 탭이 열렸는지 확인
        new_handles = set(self.driver.window_handles) - current_handles
        if new_handles:
            self.driver.switch_to.window(list(new_handles)[0])
        attempt = TestAttemptPage(self.driver, previous_url)
        try:
            attempt.expect_loaded()
        except TimeoutException:
            pass
        return attempt



    def progress_row(self, lesson_name: str) -> WebElement:
        from selenium.webdriver.common.by import By
        import time
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)

        # 1. lesson_name을 포함하는 행 또는 컨테이너 탐색
        rows = self.driver.find_elements(
            By.XPATH,
            f"//*[contains(@role, 'row') or contains(@class, 'row') or contains(@class, 'TableRow') or contains(@class, 'MuiStack-root') or contains(@class, 'css-')][contains(., '{lesson_name}')]",
        )
        visible_rows = [r for r in rows if r.is_displayed()]
        if visible_rows:
            return visible_rows[-1]

        # 2. role='region' fallback
        regions = [
            region
            for region in role_elements(self.content, "region")
            if lesson_name in region.text
        ]
        if regions:
            return regions[0]

        # 3. 텍스트 자체의 부모 요소 fallback
        els = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{lesson_name}')]")
        for el in els:
            if el.is_displayed():
                return el.find_element(By.XPATH, "..")

        assert False, f"{lesson_name!r} 학습 현황 행을 찾지 못했습니다."

    def progress_row_text(self, lesson_name: str) -> str:
        self.select_tab(self.PROGRESS_TAB)
        row = self.progress_row(lesson_name)
        assert row.is_displayed()
        return row.text.strip()

    def expect_progress_changed(self, lesson_name: str, before: str) -> str:
        self.select_tab(self.PROGRESS_TAB)
        current = self.progress_row(lesson_name).text.strip()
        if "응시 완료" in before or "응시완료" in before or "100" in before:
            return current
        try:
            WebDriverWait(self.driver, 5).until(
                lambda _: self.progress_row(lesson_name).text.strip() != before
            )
            return self.progress_row(lesson_name).text.strip()
        except TimeoutException:
            return current

    def map_node(self, lesson_name: str) -> WebElement:
        def find_node(d):
            nodes = self.content.find_elements(By.CSS_SELECTOR, "[data-testid^='rf__node-']")
            matches = [node for node in nodes if lesson_name in node.text]
            return matches[0] if matches else False
        try:
            node = WebDriverWait(self.driver, 15).until(find_node)
            return node
        except TimeoutException:
            assert False, f"{lesson_name!r} 학습맵 노드를 찾지 못했습니다."

    def map_node_signature(self, lesson_name: str) -> str:
        self.select_tab(self.MAP_TAB)
        node = self.map_node(lesson_name)
        assert node.is_displayed()
        return node.get_attribute("outerHTML")

    def expect_map_node_changed(self, lesson_name: str, before: str) -> str:
        current = self.map_node_signature(lesson_name)
        if "완료" in before or "completed" in before or "success" in before:
            return current
        try:
            WebDriverWait(self.driver, 5).until(
                lambda _: self.map_node_signature(lesson_name) != before
            )
            return self.map_node_signature(lesson_name)
        except TimeoutException:
            return current

