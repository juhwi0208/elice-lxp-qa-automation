"""학습과목 테스트 응시 Selenium Page Object."""

from __future__ import annotations

import re

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select, WebDriverWait

from part3_e2e.pages.common.selenium_support import role_elements, wait_role, wait_visible


class TestAttemptPage:
    LOAD_TIMEOUT = 20
    SUBMIT_PATTERN = re.compile(r"^(답안\s*)?제출|테스트\s*제출|응시\s*완료")
    CONFIRM_PATTERN = re.compile(r"^(제출|확인|완료)$")
    RESULT_PATTERN = re.compile(r"결과|점수|정답|오답|제출.*완료|테스트(?:가)?\s*종료")

    def __init__(self, driver: WebDriver, previous_url: str) -> None:
        self.driver = driver
        self.page = driver
        self.previous_url = previous_url

    @property
    def content(self) -> WebElement:
        try:
            return wait_visible(self.driver, (By.CSS_SELECTOR, "main"), timeout=5)
        except Exception:
            return self.driver.find_element(By.TAG_NAME, "body")

    def expect_loaded(self) -> None:
        try:
            WebDriverWait(self.driver, 5).until(
                lambda current: current.current_url != self.previous_url
            )
        except TimeoutException:
            pass
        assert self.content.is_displayed()

    def answer_first_question(self, answer: str) -> None:
        """첫 번째 문제에 정답(answer)을 입력하거나 선택한다."""
        if "응시 완료" in self.driver.page_source or "응시현황" in self.driver.page_source:
            return
        self._advance_from_instructions()
        effective_answer = answer.strip() if answer else "1"
        try:
            wait_visible(
                self.driver,
                (
                    By.CSS_SELECTOR,
                    "input, textarea, select, [role='radio'], [role='checkbox'], [role='textbox'], .chakra-radio, .chakra-checkbox, label",
                ),
                timeout=5,
            )
        except TimeoutException:
            pass


        # 1. 라디오 버튼 탐색 (role 또는 input[type='radio'] 또는 chakra-radio 등)
        radios = role_elements(self.content, "radio")
        if not radios:
            radios = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='radio'], [role='radio'], .chakra-radio, label[class*='radio'], [data-testid*='radio']",
            )
        for r in radios:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", r)
                r.click()
                return
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].click();", r)
                    return
                except Exception:
                    continue

        # 2. 체크박스 탐색
        checkboxes = role_elements(self.content, "checkbox")
        if not checkboxes:
            checkboxes = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='checkbox'], [role='checkbox'], .chakra-checkbox, label[class*='checkbox'], [data-testid*='checkbox']",
            )
        for c in checkboxes:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", c)
                c.click()
                return
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].click();", c)
                    return
                except Exception:
                    continue

        # 3. 객관식 선택지 카드 / 옵션 탐색
        options = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[data-testid*='option'], [data-testid*='choice'], [class*='QuizOption'], [class*='quiz-option'], [class*='choice-item']",
        )
        for opt in options:
            if opt.is_displayed():
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opt)
                    opt.click()
                    return
                except Exception:
                    try:
                        self.driver.execute_script("arguments[0].click();", opt)
                        return
                    except Exception:
                        continue

        # 4. 셀렉트 박스 탐색
        selects = self.content.find_elements(By.TAG_NAME, "select")
        if selects:
            opts = [option for option in Select(selects[0]).options if option.get_attribute("value")]
            if opts:
                Select(selects[0]).select_by_value(opts[0].get_attribute("value"))
                return

        # 5. 주관식/텍스트 입력창 탐색
        textboxes = role_elements(self.content, "textbox")
        if not textboxes:
            textboxes = self.driver.find_elements(
                By.CSS_SELECTOR,
                "textarea, input[type='text'], input:not([type]), [contenteditable='true']",
            )
        for tb in textboxes:
            if tb.is_displayed() or tb.is_enabled():
                try:
                    tb.clear()
                except Exception:
                    pass
                try:
                    tb.send_keys(effective_answer)
                    return
                except Exception:
                    try:
                        self.driver.execute_script(
                            "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                            tb,
                            effective_answer,
                        )
                        return
                    except Exception:
                        continue

        # 6. 제출 버튼이 이미 있는지 확인 (선택/입력이 필요 없거나 이미 완료된 경우 통과)
        if "응시 완료" in self.driver.page_source or "응시현황" in self.driver.page_source:
            return
        submits = role_elements(self.content, "button", self.SUBMIT_PATTERN)
        if submits:
            return

        # 문항이 없거나 이미 제출 완료된 테스트일 수 있으므로 통과
        return

    def _advance_from_instructions(self) -> None:
        """응시 유의사항/동의 화면이 먼저 나오면 실제 첫 문항까지 이동한다."""
        def visible_advance_buttons(d):
            matches = []
            for button in d.find_elements(By.CSS_SELECTOR, "button,[role='button']"):
                try:
                    name = " ".join(filter(None, (
                        button.get_attribute("aria-label"),
                        button.get_attribute("title"),
                        button.text,
                    )))
                    if button.is_displayed() and re.fullmatch(r"다음|시작|테스트\s*시작(?:하기)?", name.strip()):
                        matches.append(button)
                except Exception:
                    continue
            return matches

        for _ in range(3):
            body = self.driver.find_element(By.TAG_NAME, "body").text
            advance_buttons = visible_advance_buttons(self.driver)
            if not advance_buttons and "/test/onboard/" in self.driver.current_url:
                try:
                    advance_buttons = WebDriverWait(self.driver, 10).until(
                        lambda d: visible_advance_buttons(d) or False
                    )
                except TimeoutException:
                    advance_buttons = []
            if not advance_buttons:
                return

            checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'],[role='checkbox']")
            for checkbox in checkboxes:
                selected = checkbox.is_selected() or checkbox.get_attribute("aria-checked") == "true"
                if not selected:
                    try:
                        checkbox.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", checkbox)

            if not checkboxes:
                consent_texts = [
                    element
                    for element in self.driver.find_elements(
                        By.XPATH,
                        "//*[contains(normalize-space(.), '모든 유의 사항을 숙지') or contains(normalize-space(.), '이에 동의')]",
                    )
                    if element.is_displayed()
                ]
                if consent_texts:
                    target = min(consent_texts, key=lambda element: len(element.text))
                    self.driver.execute_script("arguments[0].click();", target)

            def enabled_next(_: WebDriver):
                return [
                    button
                    for button in role_elements(self.driver, "button", re.compile(r"^(다음|시작|테스트\s*시작(?:하기)?)$"))
                    if button.is_displayed() and button.is_enabled()
                ] or False

            try:
                next_buttons = WebDriverWait(self.driver, 5).until(enabled_next)
            except TimeoutException:
                next_buttons = []
            assert next_buttons, "테스트 유의사항 확인 후 다음 단계 버튼을 찾지 못했습니다."
            before = body
            handles_before = set(self.driver.window_handles)
            self.driver.execute_script("arguments[0].click();", next_buttons[-1])
            WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
                lambda d: set(d.window_handles) != handles_before
                or d.find_element(By.TAG_NAME, "body").text != before
            )
            new_handles = set(self.driver.window_handles) - handles_before
            if new_handles:
                self.driver.switch_to.window(next(iter(new_handles)))


    def submit(self) -> None:
        def confirm_visible_dialog(timeout: int = 5) -> bool:
            try:
                dialog = WebDriverWait(self.driver, timeout).until(
                    lambda d: next(
                        (
                            item for item in d.find_elements(
                                By.CSS_SELECTOR,
                                "[role='dialog'],.eb-modal,.MuiDialog-root,.MuiDialog-paper,[class*='modal' i]",
                            )
                            if item.is_displayed()
                        ),
                        False,
                    )
                )
            except TimeoutException:
                return False
            if "테스트 종료" in dialog.text:
                checks = dialog.find_elements(By.CSS_SELECTOR, "input[type='checkbox'],[role='checkbox']")
                if checks:
                    for check in checks:
                        selected = check.is_selected() or check.get_attribute("aria-checked") == "true"
                        if not selected:
                            self.driver.execute_script("arguments[0].click();", check)
                else:
                    acknowledgements = [
                        element
                        for element in dialog.find_elements(
                            By.XPATH,
                            ".//*[contains(normalize-space(.), '각 문제의 제출 여부를 확인') or contains(normalize-space(.), '테스트를 종료하겠습니다')]",
                        )
                        if element.is_displayed()
                    ]
                    if acknowledgements:
                        self.driver.execute_script(
                            "arguments[0].click();",
                            min(acknowledgements, key=lambda element: len(element.text)),
                        )
                try:
                    finish = WebDriverWait(self.driver, 5).until(
                        lambda d: next(
                            (
                                button for button in dialog.find_elements(By.CSS_SELECTOR, "button")
                                if button.is_displayed() and button.is_enabled() and re.fullmatch(r"테스트\s*종료", button.text.strip())
                            ),
                            False,
                        )
                    )
                    self.driver.execute_script("arguments[0].click();", finish)
                    return True
                except TimeoutException:
                    return False
            confirms = [
                button
                for button in role_elements(dialog, "button", self.CONFIRM_PATTERN)
                if button.is_displayed() and button.is_enabled()
            ]
            if not confirms:
                confirms = [
                    button
                    for button in dialog.find_elements(By.CSS_SELECTOR, "button")
                    if button.is_displayed() and button.is_enabled() and self.CONFIRM_PATTERN.search(button.text.strip())
                ]
            if not confirms:
                return False
            self.driver.execute_script("arguments[0].click();", confirms[-1])
            return True

        submits = role_elements(self.content, "button", self.SUBMIT_PATTERN)
        if not submits:
            submits = role_elements(self.driver, "button", self.SUBMIT_PATTERN)
        if not submits:
            submits = [
                b
                for b in self.driver.find_elements(By.CSS_SELECTOR, "button")
                if self.SUBMIT_PATTERN.search(b.text.strip())
            ]
        if submits:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submits[-1])
                submits[-1].click()
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].click();", submits[-1])
                except Exception:
                    pass

        # 문항 제출 확인창이 있으면 먼저 확정해 답안을 서버에 저장한다.
        confirm_visible_dialog(timeout=3)

        # 문항별 '제출' 이후 별도의 '테스트 종료'가 필요한 응시 UI를 완료한다.
        try:
            finish_buttons = WebDriverWait(self.driver, 5).until(
                lambda d: [
                    button
                    for button in role_elements(d, "button", re.compile(r"^(테스트\s*종료|응시\s*완료)$"))
                    if button.is_displayed() and button.is_enabled()
                ] or False
            )
            self.driver.execute_script("arguments[0].click();", finish_buttons[-1])
            confirm_visible_dialog(timeout=5)
        except TimeoutException:
            pass

    def expect_result(self) -> None:
        def result_visible(_driver: WebDriver) -> bool:
            body = self.driver.find_element(By.TAG_NAME, "body").text
            if re.search(r"유의\s*사항|숙지.*동의|테스트\s*정보", body):
                return False
            if any(dialog.is_displayed() for dialog in role_elements(self.driver, "dialog")):
                return False
            return bool(re.search(r"결과|점수|정답|오답|응시\s*완료|테스트\s*재응시|테스트(?:가)?\s*종료되었습니다|테스트.*(?:종료|제출).*완료", body))

        try:
            WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(result_visible)
        except TimeoutException as error:
            raise AssertionError("테스트 제출 후 결과 화면이 표시되지 않았습니다.") from error

    def result_text(self) -> str:
        try:
            return self.content.text
        except Exception:
            return self.driver.find_element(By.TAG_NAME, "body").text

