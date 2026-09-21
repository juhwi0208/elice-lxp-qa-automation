"""
class_schedule_page.py
수업 일정 캘린더 화면 Page Object.

담당 기능:
  - 수업 일정 화면 진입 및 로드 확인
  - 캘린더 기간 이동(이전·다음·오늘)
  - 보기 전환(캘린더·목록) 및 주말 표시 토글
  - 일정 카드 조회·클릭·상세 확인
  - 교육자 CRUD UI (만들기·수정·삭제·폼 입력)
  - 빈 상태 및 학습자 권한 차단 확인
"""

from __future__ import annotations

import re
import uuid

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

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

_LOAD_TIMEOUT = 10
_SCHEDULE_SECTION = "schedules"

# 일정 카드를 잡을 CSS 셀렉터 (서비스 DOM 구조에 맞게 조정 가능)
_CARD_SELECTOR = (
    "[data-testid='schedule-card'], "
    "[class*='ScheduleCard'], "
    "[class*='schedule-card'], "
    "[class*='schedule-item'], "
    "[class*='event']"
)


class ClassSchedulePage:
    """수업 일정 캘린더와 목록 화면을 조작한다."""

    def __init__(self, app: AppShell) -> None:
        self.app = app
        self.driver = app.driver

    # ──────────────────────────────────────────────
    # 화면 이동
    # ──────────────────────────────────────────────

    def open(self) -> None:
        """수업 일정 화면으로 직접 이동하고 로드를 기다린다."""
        if self.app.classroom_path not in self.driver.current_url:
            self.app.open_classroom()
        self.app.open_classroom_section(_SCHEDULE_SECTION)
        self.wait_until_loaded()

    def wait_until_loaded(self) -> None:
        """수업 일정 URL이 활성화되고 로딩이 끝날 때까지 대기한다."""
        for attempt in range(2):
            WebDriverWait(self.driver, _LOAD_TIMEOUT).until(
                lambda d: _SCHEDULE_SECTION in d.current_url
            )
            try:
                WebDriverWait(self.driver, _LOAD_TIMEOUT).until(
                    lambda d: not any(
                        e.is_displayed()
                        for e in d.find_elements(
                            By.CSS_SELECTOR, "[role='progressbar'], .MuiCircularProgress-root, svg.animate-spin"
                        )
                    )
                )
                # URL만 바뀌고 앱 셸/도구막대가 비어 있는 부분 렌더링 상태를
                # 로드 완료로 취급하지 않는다.
                WebDriverWait(self.driver, _LOAD_TIMEOUT).until(
                    lambda d: "수업 일정" in d.find_element(By.TAG_NAME, "body").text
                    and re.search(r"\d{4}년\s*\d{1,2}월", d.find_element(By.TAG_NAME, "body").text)
                    and any(
                        b.is_displayed() and re.search(r"오늘|today", (b.text or "") + " " + (b.get_attribute("aria-label") or ""), re.I)
                        for b in d.find_elements(By.CSS_SELECTOR, "button,[role='button']")
                    )
                )
                return
            except TimeoutException:
                if attempt:
                    raise
                self.driver.refresh()

    def reload(self) -> None:
        """수업 일정 화면을 새로고침하고 다시 로드를 기다린다."""
        self.driver.refresh()
        self.wait_until_loaded()

    # ──────────────────────────────────────────────
    # 캘린더 탐색
    # ──────────────────────────────────────────────

    def go_to_next_period(self) -> None:
        """다음 기간으로 이동하는 버튼을 클릭한다."""
        import time
        for _ in range(5):
            next_btns = self.driver.find_elements(
                By.XPATH,
                "//button[descendant::*[contains(translate(@data-testid,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chevron') and contains(translate(@data-testid,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'right')]] | "
                "//button[contains(@class, 'fc-next-button')] | "
                "//button[contains(@aria-label, 'next') or contains(@aria-label, '다음')]",
            )
            for b in next_btns:
                if b.is_displayed():
                    click_when_ready(self.driver, b)
                    return
            time.sleep(0.5)
        btns = role_elements(self.driver, "button", re.compile(r"다음|next|>", re.I))
        if btns:
            click_when_ready(self.driver, btns[0])

    def go_to_prev_period(self) -> None:
        """이전 기간으로 이동하는 버튼을 클릭한다."""
        import time
        for _ in range(5):
            prev_btns = self.driver.find_elements(
                By.XPATH,
                "//button[descendant::*[contains(translate(@data-testid,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chevron') and contains(translate(@data-testid,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'left')]] | "
                "//button[contains(@class, 'fc-prev-button')] | "
                "//button[contains(@aria-label, 'prev') or contains(@aria-label, '이전')]",
            )
            for b in prev_btns:
                if b.is_displayed():
                    click_when_ready(self.driver, b)
                    return
            time.sleep(0.5)
        btns = role_elements(self.driver, "button", re.compile(r"이전|prev|<", re.I))
        if btns:
            click_when_ready(self.driver, btns[0])

    def go_to_today(self) -> None:
        """오늘 버튼을 클릭해 오늘이 포함된 기간으로 복귀한다."""
        import time
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        for _ in range(5):
            today_btns = self.driver.find_elements(
                By.XPATH,
                "//button[normalize-space(.)='오늘' or normalize-space(.)='Today'] | "
                "//button[contains(@class, 'fc-today-button')]",
            )
            for b in today_btns:
                if b.is_displayed():
                    click_when_ready(self.driver, b)
                    return
            time.sleep(0.5)
        btns = role_elements(self.driver, "button", re.compile(r"오늘|today", re.I))
        if btns:
            click_when_ready(self.driver, btns[0])

    # ──────────────────────────────────────────────
    # 보기 설정
    # ──────────────────────────────────────────────

    def switch_to_list_view(self) -> None:
        """목록 보기로 전환한다."""
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        if not self._calendar_grid_visible():
            self._wait_view_ready()
            return
        try:
            btns = role_elements(self.driver, "button", re.compile(r"목록|list", re.I))
        except Exception:
            btns = []
        if btns:
            click_when_ready(self.driver, btns[0])
        else:
            self._click_icon_view_toggle(list_view=True)
        WebDriverWait(self.driver, _LOAD_TIMEOUT).until(lambda _: not self._calendar_grid_visible())
        self._wait_view_ready()

    def switch_to_calendar_view(self) -> None:
        """캘린더 보기로 전환한다."""
        if self._calendar_grid_visible():
            self._wait_view_ready()
            return
        try:
            btns = role_elements(self.driver, "button", re.compile(r"캘린더|calendar", re.I))
        except Exception:
            btns = []
        if btns:
            click_when_ready(self.driver, btns[0])
        else:
            self._click_icon_view_toggle(list_view=False)
        WebDriverWait(self.driver, _LOAD_TIMEOUT).until(lambda _: self._calendar_grid_visible())
        self._wait_view_ready()

    def _wait_view_ready(self) -> None:
        """보기 전환 뒤 로딩 화면이 실제 일정 내용으로 교체될 때까지 기다린다."""
        try:
            WebDriverWait(self.driver, _LOAD_TIMEOUT).until(
                lambda d: not any(
                    element.is_displayed()
                    for element in d.find_elements(
                        By.CSS_SELECTOR, "[role='progressbar'],.MuiCircularProgress-root,svg.animate-spin"
                    )
                )
                and "수업 일정" in d.find_element(By.TAG_NAME, "body").text
                and re.search(r"\d{4}년\s*\d{1,2}월", d.find_element(By.TAG_NAME, "body").text)
            )
        except TimeoutException:
            self.driver.refresh()
            self.wait_until_loaded()

    def _calendar_grid_visible(self) -> bool:
        return len([
            element for element in self.driver.find_elements(By.CSS_SELECTOR, "[data-date],thead th,[role='columnheader']")
            if element.is_displayed()
        ]) >= 5

    def _click_icon_view_toggle(self, *, list_view: bool) -> None:
        """접근 가능한 이름이 없는 캘린더/목록 아이콘 토글을 조작한다."""
        def find_buttons(d):
            found = []
            for button in d.find_elements(By.CSS_SELECTOR, "main button"):
                try:
                    if button.is_displayed() and button.rect["y"] < 220 and not button.text.strip() and button.find_elements(By.CSS_SELECTOR, "svg"):
                        found.append(button)
                except Exception:
                    continue
            return found if len(found) >= 2 else False

        buttons = WebDriverWait(self.driver, _LOAD_TIMEOUT).until(find_buttons)
        rightmost = sorted(buttons, key=lambda button: button.rect["x"])[-2:]
        click_when_ready(self.driver, rightmost[1 if list_view else 0])

    def toggle_weekend(self) -> None:
        """주말 표시 설정을 전환한다."""
        # 1. role="button" 또는 button 요소 시도
        btns = role_elements(self.driver, "button", re.compile(r"주말", re.I))
        if btns:
            click_when_ready(self.driver, btns[0])
            return

        # 2. '주말' 텍스트를 포함하는 label, checkbox, switch 탐색
        candidates = self.driver.find_elements(
            By.XPATH,
            "//*[contains(., '주말')]/ancestor-or-self::*[self::label or self::button or contains(@class, 'Switch') or contains(@class, 'Checkbox') or @role='switch'][1]"
        )
        for c in candidates:
            if c.is_displayed():
                click_when_ready(self.driver, c)
                return

        # 3. fallback: 일반 텍스트 노드 클릭
        elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), '주말')]")
        for el in elems:
            if el.is_displayed():
                click_when_ready(self.driver, el)
                return

    # ──────────────────────────────────────────────
    # 일정 카드
    # ──────────────────────────────────────────────

    def get_schedule_cards(self) -> list[WebElement]:
        """현재 화면에 보이는 일정 카드 요소 목록을 반환한다."""
        return [
            e for e in self.driver.find_elements(By.CSS_SELECTOR, _CARD_SELECTOR)
            if e.is_displayed()
        ]

    def has_schedule_cards(self) -> bool:
        """현재 화면에 일정 카드가 하나 이상 있는지 확인한다."""
        return len(self.get_schedule_cards()) > 0

    def click_first_schedule_card(self) -> None:
        """첫 번째 일정 카드를 클릭해 상세 화면을 연다."""
        cards = self.get_schedule_cards()
        assert cards, "클릭할 수 있는 일정 카드가 없습니다."
        click_when_ready(self.driver, lambda: self.get_schedule_cards()[0])

    def click_schedule_card_by_title(self, title: str) -> None:
        """특정 제목이 포함된 일정 카드를 클릭한다."""
        card = wait_text(self.driver, self.driver, title, exact=False)
        click_when_ready(self.driver, card)

    def get_card_count(self) -> int:
        """현재 화면에 표시된 일정 카드 수를 반환한다."""
        return len(self.get_schedule_cards())

    # ──────────────────────────────────────────────
    # 상세 패널
    # ──────────────────────────────────────────────

    def get_detail_title(self) -> str:
        """일정 상세 패널 또는 모달에서 제목 텍스트를 반환한다."""
        heading = wait_role(self.driver, self.driver, "heading")
        return heading.text.strip()

    def get_detail_time(self) -> str:
        """일정 상세에서 시간 텍스트를 반환한다."""
        candidates = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[data-testid='schedule-time'], [class*='schedule-time'], [class*='ScheduleTime'], time"
        )
        visible = [e for e in candidates if e.is_displayed() and e.text.strip()]
        if visible:
            return visible[0].text.strip()
        containers = [
            d for d in self.driver.find_elements(
                By.CSS_SELECTOR,
                "[role='dialog'],.MuiDialog-paper,.MuiPopover-paper,[class*='Modal'],aside,[class*='detail'],[class*='Detail']",
            )
            if d.is_displayed() and d.text.strip()
        ]
        texts = [d.text.strip() for d in containers]
        texts.append(self.driver.find_element(By.TAG_NAME, "body").text.strip())
        for text in texts:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            time_lines = [
                line for line in lines
                if re.search(r"(?:오전|오후)\s*\d{1,2}:\d{2}|\b\d{1,2}:\d{2}\b", line)
            ]
            if time_lines:
                return "\n".join(time_lines)
        return texts[0] if texts else ""

    def close_detail(self) -> None:
        """일정 상세 닫기 버튼을 클릭한다."""
        btns = role_elements(self.driver, "button", re.compile(r"닫기|close|×|✕", re.I))
        if btns:
            click_when_ready(self.driver, btns[-1])

    # ──────────────────────────────────────────────
    # 빈 상태
    # ──────────────────────────────────────────────

    def is_empty_state_visible(self) -> bool:
        """일정 없음 빈 상태 메시지가 표시되는지 확인한다."""
        candidates = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '일정이 없') or "
            "contains(normalize-space(.), '수업 일정이 없') or "
            "contains(normalize-space(.), '등록된 일정')]"
        )
        return any(e.is_displayed() for e in candidates)

    # ──────────────────────────────────────────────
    # 교육자 CRUD UI
    # ──────────────────────────────────────────────

    def is_create_button_visible(self, timeout: int = 10) -> bool:
        """교육자 전용 만들기 버튼이 화면에 있는지 확인한다 (권한 경계 검증용)."""
        def find_btn(d):
            btns = [
                b
                for b in d.find_elements(By.CSS_SELECTOR, "button")
                if ("만들기" in b.text or "추가" in b.text)
                and b.is_displayed()
                and b.is_enabled()
            ]
            return len(btns) > 0

        try:
            return WebDriverWait(self.driver, timeout).until(find_btn)
        except TimeoutException:
            return False

    def click_create_schedule_button(self) -> None:
        """일정 만들기 버튼을 클릭한다."""
        btns = [
            b
            for b in self.driver.find_elements(By.CSS_SELECTOR, "button")
            if ("만들기" in b.text or "추가" in b.text) and b.is_displayed()
        ]
        if not btns:
            btns = role_elements(self.driver, "button", re.compile(r"만들기|추가", re.I))

        assert btns, "일정 만들기 버튼을 찾지 못했습니다."
        target_btn = btns[0]
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_btn)
            target_btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", target_btn)

        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: any(
                    dlg.is_displayed()
                    for dlg in d.find_elements(By.CSS_SELECTOR, "[role='dialog'], .MuiDialog-root")
                )
            )
        except TimeoutException:
            pass

    def fill_schedule_form(
        self, *, title: str, description: str = "", is_allday: bool = False, is_recurring: bool = False
    ) -> None:
        """일정 생성/수정 폼에 제목과 설명, 종일/반복 옵션을 입력한다."""
        from selenium.webdriver.common.keys import Keys
        import time

        # 종일 및 반복 체크박스 처리
        if is_allday or is_recurring:
            labels = self.driver.find_elements(By.TAG_NAME, "label")
            for label in labels:
                text = label.text
                try:
                    cb = label.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                    if "종일" in text and is_allday:
                        if not cb.is_selected():
                            self.driver.execute_script("arguments[0].click();", cb)
                    elif "반복" in text and is_recurring:
                        if not cb.is_selected():
                            self.driver.execute_script("arguments[0].click();", cb)
                except Exception:
                    continue
            time.sleep(0.5)

        # 생성(dialog) 및 수정(popover) 폼의 제목 입력창(name='summary' 또는 placeholder) 탐색
        title_input = WebDriverWait(self.driver, 10).until(
            lambda d: next(
                (
                    inp for inp in d.find_elements(
                        By.CSS_SELECTOR,
                        "input[name='summary'], [role='dialog'] input[placeholder*='제목'], .MuiPopover-paper input[placeholder*='제목']"
                    )
                    if inp.is_displayed() and inp.is_enabled()
                ),
                None
            )
        )
        assert title_input is not None, "일정 제목 입력창을 찾지 못했습니다."

        # 스크롤을 올려 제목창을 뷰포트 안으로 가져옴
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", title_input)
        except Exception:
            pass

        try:
            title_input.clear()
        except Exception:
            pass
        try:
            title_input.send_keys(Keys.CONTROL, "a")
            title_input.send_keys(Keys.BACKSPACE)
        except Exception:
            pass
        title_input.send_keys(title)
        try:
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
                "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                title_input,
            )
        except Exception:
            pass

        if description:
            desc_inputs = [
                inp for inp in self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[role='dialog'] textarea, .MuiPopover-paper textarea, [role='dialog'] [contenteditable='true'], .MuiPopover-paper [contenteditable='true']"
                )
                if inp.is_displayed() and inp.is_enabled()
            ]
            if desc_inputs:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", desc_inputs[0])
                except Exception:
                    pass
                try:
                    desc_inputs[0].clear()
                except Exception:
                    pass
                desc_inputs[0].send_keys(description)
                try:
                    self.driver.execute_script(
                        "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
                        "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                        desc_inputs[0],
                    )
                except Exception:
                    pass

    def get_form_error_messages(self) -> list[str]:
        """일정 폼 내의 필수값 누락 등 유효성 검사 에러 텍스트들을 추출한다."""
        errors = self.driver.find_elements(By.CSS_SELECTOR, ".Mui-error, [class*='error-message'], [class*='helper-text']")
        return [e.text.strip() for e in errors if e.is_displayed() and e.text.strip()]

    def submit_schedule_form(self, *, allow_disabled: bool = False) -> None:
        """일정 생성/수정 폼의 저장 버튼을 클릭한다."""
        import time

        # 1. 팝업/다이얼로그 컨테이너 내부에서 저장 버튼 우선 탐색 (최상단 모달부터 역순)
        containers = [
            c for c in self.driver.find_elements(
                By.CSS_SELECTOR,
                "[role='dialog'], .MuiPopover-paper, .MuiDialog-paper, .MuiModal-root"
            ) if c.is_displayed()
        ]
        target_btn = None
        for c in reversed(containers):
            for b in c.find_elements(By.TAG_NAME, "button"):
                txt = b.text.strip()
                cls = b.get_attribute("class") or ""
                if b.is_displayed() and ("저장" in txt or "MuiLoadingButton" in cls or "submit" in txt):
                    if "취소" not in txt:
                        target_btn = b
                        break
            if target_btn:
                break

        # 2. 컨테이너에서 못 찾았을 경우 전체 DOM에서 가시적인 저장 버튼 탐색
        if target_btn is None:
            for b in self.driver.find_elements(By.TAG_NAME, "button"):
                txt = b.text.strip()
                cls = b.get_attribute("class") or ""
                if b.is_displayed() and ("저장" in txt or "MuiLoadingButton" in cls or "submit" in txt):
                    if "취소" not in txt:
                        target_btn = b
                        break

        assert target_btn is not None, "일정 저장 버튼을 찾지 못했습니다."
        if not target_btn.is_enabled():
            if allow_disabled:
                return
            raise AssertionError("일정 저장 버튼이 비활성화되어 있습니다.")
        try:
            target_btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", target_btn)

        # 팝업/다이얼로그 닫힘 대기
        try:
            WebDriverWait(self.driver, 5).until(
                lambda d: not any(
                    dlg.is_displayed()
                    for dlg in d.find_elements(By.CSS_SELECTOR, "[role='dialog'], .MuiPopover-paper")
                )
            )
        except Exception:
            pass
        time.sleep(2)
        self.open()
        self.wait_until_loaded()

    def cancel_schedule_form(self) -> None:
        """일정 생성/수정 폼의 취소 버튼을 클릭한다."""
        import time

        dialog = None
        for d in self.driver.find_elements(By.XPATH, "//*[@role='dialog']"):
            if d.is_displayed():
                dialog = d
                break
        ctx = dialog if dialog else self.driver
        btns = [b for b in ctx.find_elements(By.TAG_NAME, "button") if "취소" in b.text and b.is_displayed()]
        if btns:
            try:
                btns[0].click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", btns[0])

        try:
            WebDriverWait(self.driver, 5).until(
                lambda d: not any(dlg.is_displayed() for dlg in d.find_elements(By.XPATH, "//*[@role='dialog']"))
            )
        except Exception:
            pass
        time.sleep(1)
        if _SCHEDULE_SECTION not in self.driver.current_url:
            self.app.open_classroom()
            self.open()

    def _open_more_popovers_if_needed(self) -> None:
        """+more 링크가 있으면 클릭하여 숨겨진 일정들을 펼친다."""
        more_links = self.driver.find_elements(By.CSS_SELECTOR, ".fc-more-link, [class*='more-link']")
        for link in more_links:
            if link.is_displayed():
                try:
                    self.driver.execute_script("arguments[0].click();", link)
                    break
                except Exception:
                    pass

    def click_schedule_card_by_title(self, title: str) -> None:
        """특정 제목이 포함된 일정 카드를 클릭한다."""
        import time

        time.sleep(1)
        hex_match = re.search(r"[0-9a-f]{8}", title)
        hex_key = hex_match.group(0) if hex_match else ""

        card = None
        search_queries = [title]
        if hex_key:
            search_queries.append(hex_key)

        for _ in range(2):
            for query in search_queries:
                cards = [
                    c
                    for c in self.driver.find_elements(By.XPATH, f"//*[contains(., '{query}')]")
                    if c.tag_name.lower() not in ("body", "html", "main", "header", "nav", "script", "style")
                ]
                if cards:
                    card = cards[-1]
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    except Exception:
                        pass
                    break
            if card:
                break
            self._open_more_popovers_if_needed()
            time.sleep(0.5)

        assert card, f"제목 '{title}'인 일정 카드를 찾지 못했습니다."
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            card.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", card)

    def is_title_present_in_calendar(self, title: str, timeout: int = 10) -> bool:
        """달력 또는 목록에서 특정 제목의 일정 카드가 표시되는지 확인한다."""
        import re

        hex_match = re.search(r"[0-9a-f]{8}", title)
        hex_key = hex_match.group(0) if hex_match else title

        def check(d):
            # 1. body 텍스트에서 즉시 확인
            try:
                body_text = d.find_element(By.TAG_NAME, "body").text
                if hex_key in body_text or title in body_text:
                    return True
            except Exception:
                pass

            if hex_key in d.page_source or title in d.page_source:
                return True

            # 2. DOM 요소 확인
            cards = [
                c
                for c in d.find_elements(By.XPATH, f"//*[contains(., '{hex_key}')]")
                if c.tag_name.lower() not in ("body", "html", "main", "header", "nav", "script", "style")
            ]
            if cards:
                return True
            self._open_more_popovers_if_needed()
            return False

        try:
            return WebDriverWait(self.driver, timeout).until(check)
        except TimeoutException:
            return False

    def wait_title_disappears(self, title: str, timeout: int = 10) -> bool:
        """달력에서 특정 제목의 일정이 사라질 때까지 대기한다."""
        import re

        hex_match = re.search(r"[0-9a-f]{8}", title)
        hex_key = hex_match.group(0) if hex_match else title

        def check_disappeared(d):
            cards = [
                c
                for c in d.find_elements(By.XPATH, f"//*[contains(., '{hex_key}')]")
                if c.is_displayed() and c.tag_name.lower() not in ("body", "html", "main", "header", "nav")
            ]
            return len(cards) == 0

        try:
            return WebDriverWait(self.driver, timeout).until(check_disappeared)
        except TimeoutException:
            return False

    def _get_detail_popover_buttons(self) -> list[WebElement]:
        """일정 상세 팝오버/패널 내부의 헤더 아이콘 버튼 목록을 반환한다."""
        popovers = [
            p
            for p in self.driver.find_elements(
                By.CSS_SELECTOR,
                "[role='dialog'], [role='presentation'], .MuiPopover-root, .MuiPaper-elevation, .MuiPaper-root",
            )
            if p.is_displayed() and p.size.get("width", 0) > 100
        ]
        if popovers:
            popover = popovers[-1]
            btns = [
                b
                for b in popover.find_elements(By.CSS_SELECTOR, "button, [role='button']")
                if b.is_displayed()
            ]
            if btns:
                return btns
        return []

    def click_edit_schedule(self) -> None:
        """일정 상세에서 수정 버튼을 클릭한다."""
        import time

        # pen-to-squareIcon 타겟팅
        edit_icons = self.driver.find_elements(
            By.CSS_SELECTOR,
            "svg[data-testid='pen-to-squareIcon'], [data-testid*='pen-to-square'], [data-testid*='edit' i]"
        )
        for icon in edit_icons:
            if icon.is_displayed():
                try:
                    btn = self.driver.execute_script(
                        "return arguments[0].closest('button, [role=\"button\"]') || arguments[0];",
                        icon,
                    )
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    return
                except Exception:
                    pass

        # fallback
        popover_btns = self._get_detail_popover_buttons()
        if popover_btns:
            self.driver.execute_script("arguments[0].click();", popover_btns[0])
            time.sleep(1)

    def click_delete_schedule(self) -> None:
        """일정 상세에서 삭제 버튼을 클릭한다."""
        import time

        # trashIcon 타겟팅
        trash_icons = self.driver.find_elements(
            By.CSS_SELECTOR,
            "svg[data-testid='trashIcon'], [data-testid*='trash'], [data-testid*='delete' i]"
        )
        for icon in trash_icons:
            if icon.is_displayed():
                try:
                    btn = self.driver.execute_script(
                        "return arguments[0].closest('button, [role=\"button\"]') || arguments[0];",
                        icon,
                    )
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    return
                except Exception:
                    pass

        # fallback
        popover_btns = self._get_detail_popover_buttons()
        if len(popover_btns) >= 2:
            self.driver.execute_script("arguments[0].click();", popover_btns[1])
            time.sleep(1)

    def confirm_delete(self) -> None:
        """삭제 확인 다이얼로그에서 확인 버튼을 클릭한다."""
        import time

        time.sleep(0.5)
        btns = [
            b
            for b in self.driver.find_elements(By.CSS_SELECTOR, "button, [role='button']")
            if (b.text or "").strip() in ("확인", "삭제", "OK", "Confirm") and b.is_displayed()
        ]
        if not btns:
            btns = role_elements(
                self.driver, "button", re.compile(r"^(확인|삭제|ok|confirm)$", re.I)
            )
        if btns:
            try:
                btns[-1].click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", btns[-1])
        time.sleep(2)
        if _SCHEDULE_SECTION not in self.driver.current_url:
            self.app.open_classroom()
            self.open()

    def cancel_delete(self) -> None:
        """삭제 확인 다이얼로그에서 취소 버튼을 클릭한다."""
        btns = role_elements(self.driver, "button", re.compile(r"취소|cancel", re.I))
        if btns:
            click_when_ready(self.driver, btns[0])

    # ──────────────────────────────────────────────
    # 유효성 오류 확인
    # ──────────────────────────────────────────────

    def is_form_open(self) -> bool:
        """저장 버튼이 보이면 폼이 아직 열려 있다고 판단한다."""
        save_btns = role_elements(self.driver, "button",
                                  re.compile(r"저장|확인|완료|save|submit", re.I))
        return any(b.is_displayed() for b in save_btns)

    def has_validation_error(self) -> bool:
        """필수 입력 오류 메시지가 화면에 표시되는지 확인한다."""
        errors = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '필수') or "
            "contains(normalize-space(.), '제목을 입력') or "
            "contains(normalize-space(.), '입력해주세요') or "
            "contains(normalize-space(.), 'required')]"
        )
        return any(e.is_displayed() for e in errors)



    # ──────────────────────────────────────────────
    # 편의 메서드: QA-AUTO 고유 제목 생성
    # ──────────────────────────────────────────────

    @staticmethod
    def make_qa_title(prefix: str = "일정") -> str:
        """테스트마다 고유한 [QA-AUTO] 제목 문자열을 생성한다."""
        return f"[QA-AUTO] {prefix}-{uuid.uuid4().hex[:8]}"
