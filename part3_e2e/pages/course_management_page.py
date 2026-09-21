"""교육자 학습과목·수업 공개 설정 Selenium Page Object."""

from __future__ import annotations

import re

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.common.selenium_support import (
    role_elements,
    text_elements,
    wait_role,
    wait_text,
    wait_visible,
)


class CourseManagementPage:
    SECTION = "courses"
    LOAD_TIMEOUT = 20
    SETTINGS_PATTERN = re.compile(r"수정|설정|관리")
    SAVE_PATTERN = re.compile(r"저장|완료|확인")
    PUBLIC_PATTERN = re.compile(r"공개")
    CLOSE_PATTERN = re.compile(r"닫기|취소")

    def __init__(self, app: AppShell) -> None:
        self.app = app
        self.driver = app.driver
        self.page = app.driver
        self.content = app.driver
        self.course_url = ""

    def open(self) -> None:
        self.app.open_classroom_section(self.SECTION)
        self.expect_loaded()

    def expect_loaded(self) -> None:
        wait_text(self.driver, self.content, re.compile(r"과목 추가|추가|새 과목", re.I), exact=False)

    def card(self, name: str) -> WebElement:
        """주어진 이름(name)을 포함하는 수업 카드를 반환한다."""
        pattern = re.compile(re.escape(name), re.I)
        try:
            el = wait_text(self.driver, self.content, pattern, exact=False, timeout=10)
            return self.driver.execute_script("return arguments[0].closest('button, a, [role=\"button\"], [role=\"link\"]') || arguments[0];", el)
        except Exception:
            assert False, f"{name!r} 과목 카드를 찾지 못했습니다."

    def open_course(self, course_name: str) -> None:
        current_url = self.driver.current_url
        card = self.card(course_name)
        assert card.is_displayed()
        try:
            card.click()
        except Exception:
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.common.keys import Keys
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
                pass
            self.driver.execute_script("arguments[0].click();", card)
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: d.current_url != current_url
            )
        except Exception:
            pass
        self.course_url = self.driver.current_url
        wait_text(self.driver, self.content, course_name)

    def edit_course_info(self, new_desc: str) -> None:
        """현재 열린 과목의 소개글(설명)을 수정하고 저장한다."""
        import time
        self._ensure_edit_mode()
        
        # 소개 수정 아이콘 클릭
        try:
            edit_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='소개 수정'], button .eb-icon-edit")
            if edit_btns:
                self.driver.execute_script("arguments[0].click();", edit_btns[-1])
                time.sleep(1)
        except Exception:
            pass
            
        # 텍스트에어리어 또는 인풋 찾기
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "textarea, input[type='text']")
        for inp in inputs:
            if inp.is_displayed():
                inp.send_keys(Keys.CONTROL + "a")
                inp.send_keys(Keys.DELETE)
                inp.send_keys(new_desc)
                break
                
        # 저장 버튼 클릭
        save_btns = [b for b in self.driver.find_elements(By.CSS_SELECTOR, "button") if b.is_displayed() and "저장" in b.text]
        if save_btns:
            self.driver.execute_script("arguments[0].click();", save_btns[0])
            time.sleep(1)

    def _ensure_edit_mode(self) -> None:
        """과목 편집 스위치를 켠다."""
        import time
        # 이미 편집 모드인지 확인 (목차 영역 또는 수업 추가 버튼)
        if self.driver.find_elements(By.XPATH, "//*[contains(text(), '수업 추가') or contains(text(), '수업 순서 변경')]"):
            return

        switch_inputs = self.driver.find_elements(By.CSS_SELECTOR, "label .MuiSwitch-input, input[type='checkbox']")
        for inp in switch_inputs:
            parent_label = self.driver.execute_script("return arguments[0].closest('label');", inp)
            if parent_label and "과목 편집" in parent_label.text:
                if not inp.is_selected():
                    self.driver.execute_script("arguments[0].click();", inp)
                    time.sleep(1.5)
                return

        # fallback: 텍스트로 라벨 찾아서 클릭
        labels = self.driver.find_elements(By.XPATH, "//label[contains(., '과목 편집')]")
        for lbl in labels:
            if lbl.is_displayed():
                self.driver.execute_script("arguments[0].click();", lbl)
                time.sleep(1.5)
                return

    def _ensure_lesson_edit_view(self, lesson_name: str) -> None:
        """과목 편집 모드로 진입하고 해당 수업(lesson)의 상세 편집 뷰로 이동한다."""
        import time
        if not self.driver.find_elements(By.CSS_SELECTOR, ".eb-course-lecture-header__status__badges"):
            self._ensure_edit_mode()
            time.sleep(1)
            # 사이드바/목록에서 lesson_name 클릭
            try:
                targets = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{lesson_name}')]")
                for t in targets:
                    if t.is_displayed():
                        self.driver.execute_script("arguments[0].click();", t)
                        time.sleep(1)
                        break
            except Exception:
                pass
        WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, ".eb-course-lecture-header__status__badges")
        )

    def publication_state(self, lesson_name: str) -> bool:
        """해당 수업(lesson)의 공개 상태를 반환한다 (공개: True, 비공개: False)."""
        self._ensure_lesson_edit_view(lesson_name)
        badges = self.driver.find_elements(By.CSS_SELECTOR, ".eb-course-lecture-header__status__badges .eb-badge-next")
        if badges:
            text = badges[0].text.strip()
            if "비공개" in text:
                return False
            if "공개" in text:
                return True

        dropdowns = self.driver.find_elements(By.CSS_SELECTOR, "#button-dropdown button")
        if dropdowns:
            d_text = dropdowns[0].text.strip()
            if "테스트 공개" in d_text:
                return False
            if "비공개" in d_text:
                return True

        return False

    def set_publication_state(self, lesson_name: str, is_public: bool) -> None:
        """해당 수업(lesson)의 공개 상태를 is_public으로 설정한다."""
        import time
        from selenium.webdriver.support import expected_conditions as EC

        current = self.publication_state(lesson_name)
        if current == is_public:
            return

        dropdown = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#button-dropdown button"))
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
        time.sleep(0.5)
        try:
            dropdown.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", dropdown)
        time.sleep(1)

        menu = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".ant-menu"))
        )
        target_menu_text = "공개하기" if is_public else "비공개"
        menu_items = menu.find_elements(By.CSS_SELECTOR, ".ant-menu-item")
        clicked = False
        for item in menu_items:
            if target_menu_text in item.text:
                try:
                    item.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", item)
                clicked = True
                break
        assert clicked, f"메뉴에서 '{target_menu_text}' 항목을 찾지 못했습니다."
        time.sleep(1)

        # 공개 시 나타나는 확인 모달 처리
        try:
            modal_btns = [
                b for b in self.driver.find_elements(By.CSS_SELECTOR, "button.eb-button")
                if b.is_displayed() and b.text.strip() in ("공개", "비공개", "확인")
            ]
            if modal_btns:
                try:
                    modal_btns[-1].click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", modal_btns[-1])
                time.sleep(2)
        except Exception:
            pass

        WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda _: self.publication_state(lesson_name) == is_public
        )

    def expect_publication_state(self, lesson_name: str, is_public: bool) -> None:
        """수업의 공개 상태가 is_public이 될 때까지 대기하고 검증한다."""
        WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda _: self.publication_state(lesson_name) == is_public
        )
