"""
board_page.py
게시판(공지·자유·Q&A) 화면 Page Object.

담당 기능:
  - 게시판 화면 진입 및 로드 확인
  - 게시글 목록 조회·검색·정렬 변경
  - 게시글 작성·수정·삭제 (mutating)
  - 댓글 작성·삭제 (mutating)
  - 게시글 상세 제목·본문·첨부파일·댓글 확인
  - 접근 제어 확인
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

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
    wait_visible,
)

_LOAD_TIMEOUT = 10
_BOARD_SECTION = "articles"


class BoardPage:
    """게시판 목록·상세·작성·수정·삭제 화면을 조작한다."""

    LOAD_TIMEOUT = 30
    MANAGEMENT_TEXTS = ("게시판 관리", "게시판 설정")

    def __init__(self, app: AppShell) -> None:
        self.app = app
        self.driver = app.driver

    # ──────────────────────────────────────────────
    # 화면 이동
    # ──────────────────────────────────────────────

    def open(self) -> None:
        """게시판 화면으로 이동하고 로드를 기다린다."""
        self.app.open_classroom_section(_BOARD_SECTION)
        self.wait_until_loaded()

    def wait_until_loaded(self) -> None:
        """게시판 URL이 활성화될 때까지 대기한다."""
        WebDriverWait(self.driver, _LOAD_TIMEOUT).until(
            lambda d: any(sec in d.current_url for sec in (_BOARD_SECTION, "boards"))
        )
        def board_content_ready(d) -> bool:
            if re.search(r"/articles/(?!write(?:[/?#]|$)|new(?:[/?#]|$))[^/?#]+", d.current_url):
                return any(
                    element.is_displayed() and element.text.strip()
                    for element in d.find_elements(
                        By.CSS_SELECTOR,
                        "main h1,main h2,main h3,main h4,main h5,main h6,main [class*='title']",
                    )
                )
            body = d.find_element(By.TAG_NAME, "body").text
            return "게시판" in body and (
                bool(d.find_elements(By.CSS_SELECTOR, "tbody tr"))
                or bool(d.find_elements(By.CSS_SELECTOR, "input[placeholder*='검색'],button"))
            )

        WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(board_content_ready)

    def expect_loaded(self) -> None:
        """통합 시나리오에서 사용하는 게시판 로드 검증 별칭."""
        self.wait_until_loaded()

    def reload(self) -> None:
        """게시판 화면을 새로고침하고 다시 로드를 기다린다."""
        self.driver.refresh()
        self.wait_until_loaded()

    # ──────────────────────────────────────────────
    # 목록 조회
    # ──────────────────────────────────────────────

    def get_article_titles(self) -> list[str]:
        """게시판 목록에 표시된 게시글 제목 텍스트 목록을 반환한다."""
        rows = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr")
        titles = []
        for row in rows:
            try:
                if not row.is_displayed():
                    continue
                cells = row.find_elements(By.TAG_NAME, "td")
                if cells:
                    title_text = cells[0].text.strip().splitlines()[0]
                    if title_text and not title_text.startswith("작성자") and title_text not in titles:
                        titles.append(title_text)
            except Exception:
                continue
        if titles:
            return titles

        items = self.driver.find_elements(
            By.CSS_SELECTOR,
            "main [class*='article'], main [class*='post'], main [class*='board-item'], main tr",
        )
        for item in items:
            try:
                if item.is_displayed() and item.text.strip():
                    first_line = item.text.strip().splitlines()[0]
                    if first_line and first_line not in titles:
                        titles.append(first_line)
            except Exception:
                continue
        return titles

    def _find_matching_article_elements(self, title: str) -> list[WebElement]:
        """화면 내에서 실제 게시글 항목(제목 링크/행/상세 제목) 중 title과 일치하는 요소를 반환한다.
        토스트 알림, 모달 다이얼로그, 검색창, '검색 결과 없음' 문구 등은 제외한다."""
        script = """
            var title = arguments[0];
            var elements = document.querySelectorAll('a, tr, li, h1, h2, h3, h4, h5, h6, [class*="title"], [class*="item"], [class*="row"], [class*="article"], [class*="card"], [class*="post"]');
            var matches = [];
            for (var i = 0; i < elements.length; i++) {
                var el = elements[i];
                if (el.closest('header, nav, [role="alert"], [class*="alert"], [class*="snackbar"], [class*="toast"], [role="dialog"], [class*="empty"], [class*="no-result"], [class*="no-data"]')) {
                    continue;
                }
                var tag = el.tagName.toLowerCase();
                if (tag === 'input' || tag === 'textarea' || tag === 'select') continue;

                var style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                if (el.offsetWidth === 0 && el.offsetHeight === 0) continue;
                
                var txt = el.innerText || el.textContent || '';
                if (txt.indexOf(title) !== -1) {
                    matches.push(el);
                }
            }
            return matches;
        """
        try:
            return self.driver.execute_script(script, title) or []
        except Exception:
            return []

    def is_article_visible(self, title: str, timeout: float = 5.0) -> bool:
        """목록에서 제목(title)이 표시되는지 확인한다."""
        import time
        end_time = time.time() + timeout
        while time.time() < end_time:
            elems = self._find_matching_article_elements(title)
            if elems:
                return True
            time.sleep(0.3)
        return False

    def wait_title_disappears(self, title: str, timeout: float = 10.0) -> bool:
        """게시글 삭제 후 목록에서 해당 제목이 사라질 때까지 대기한다."""
        import time
        end_time = time.time() + timeout
        while time.time() < end_time:
            elems = self._find_matching_article_elements(title)
            if not elems:
                return True
            time.sleep(0.5)
        return False

    def click_article(self, title: str) -> None:
        """특정 제목의 게시글 링크를 클릭해 상세 화면으로 이동한다.
        1페이지에 보이지 않으면 검색창을 통해 검색 후 클릭한다.
        """
        import time

        def detail_opened() -> bool:
            return bool(re.search(r"/articles/\d+(?:[/?#]|$)", self.driver.current_url))

        # 0. tbody tr 중에서 title을 포함하는 행의 실제 링크/클릭 대상을 클릭
        rows = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr")
        for row in rows:
            try:
                if row.is_displayed() and (not title or title in row.text):
                    links = row.find_elements(By.CSS_SELECTOR, "a[href*='/articles/']")
                    cells = row.find_elements(By.TAG_NAME, "td")
                    target_el = links[0] if links else (cells[0] if cells else row)
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_el)
                    time.sleep(0.3)
                    self.driver.execute_script("arguments[0].click();", target_el)
                    try:
                        WebDriverWait(self.driver, 5).until(lambda d: detail_opened())
                        return
                    except Exception:
                        pass
            except Exception:
                continue

        def find_target():
            # input이나 textarea가 아닌 실제 목록 내 제목 요소 탐색
            elems = self.driver.find_elements(
                By.XPATH,
                f"//a[contains(., '{title}')] | //*[not(self::input) and not(self::textarea)][contains(text(), '{title}')]"
            )
            for el in elems:
                if el.is_displayed() and el.tag_name.lower() not in ("input", "textarea", "header"):
                    return el
            return None

        target = None
        try:
            target = WebDriverWait(self.driver, 3).until(lambda d: find_target())
        except Exception:
            pass

        # 1페이지에 없으면 검색창을 통해 검색 시도
        if target is None:
            try:
                self.search(title)
                target = WebDriverWait(self.driver, 5).until(lambda d: find_target())
            except Exception:
                target = None

        assert target is not None, f"클릭할 게시글 '{title}' 요소를 찾지 못했습니다."

        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        except Exception:
            pass
        time.sleep(0.5)

        # 직접 클릭 시도 후 상위 tr/td 클릭
        clicked = False
        try:
            target.click()
            time.sleep(0.5)
            if detail_opened():
                clicked = True
        except Exception:
            pass

        if not clicked:
            try:
                row = target.find_element(By.XPATH, "./ancestor-or-self::tr")
                self.driver.execute_script("arguments[0].click();", row)
                time.sleep(0.5)
                if detail_opened():
                    clicked = True
            except Exception:
                pass

        if not clicked:
            try:
                cell = target.find_element(By.XPATH, "./ancestor-or-self::td")
                self.driver.execute_script("arguments[0].click();", cell)
            except Exception:
                self.driver.execute_script("arguments[0].click();", target)

        WebDriverWait(self.driver, _LOAD_TIMEOUT).until(lambda d: detail_opened())

    # ──────────────────────────────────────────────
    # 검색
    # ──────────────────────────────────────────────

    def search(self, keyword: str) -> None:
        """게시판 검색창에 키워드를 입력하고 검색한다. 빈 키워드일 경우 클리어 버튼 또는 전체 삭제 수행."""
        import time

        # 빈 키워드일 때 검색창의 X(Clear) 버튼이 있으면 먼저 클릭
        if not keyword:
            try:
                clear_btns = self.driver.find_elements(
                    By.XPATH,
                    "//button[@aria-label='clear' or @aria-label='Clear' or contains(@class, 'clear') or contains(@class, 'Clear')] | //button[descendant::svg[contains(@data-testid, 'Close') or contains(@data-testid, 'Clear')]]"
                )
                for cb in clear_btns:
                    if cb.is_displayed():
                        cb.click()
                        time.sleep(0.5)
                        break
            except Exception:
                pass

        def find_input(d):
            search_inputs = [
                i
                for i in d.find_elements(
                    By.CSS_SELECTOR,
                    "main input[placeholder*='검색'], main input[type='search'], input[placeholder*='글 검색'], input[placeholder*='검색'], input[type='search']"
                )
                if i.is_displayed()
            ]
            board_inputs = []
            for inp in search_inputs:
                is_in_header = d.execute_script(
                    "return arguments[0].closest('header, [class*=\"Header\"], [class*=\"Nav\"]') !== null;",
                    inp,
                )
                if not is_in_header:
                    board_inputs.append(inp)
            return board_inputs[0] if board_inputs else (search_inputs[0] if search_inputs else None)

        try:
            target_input = WebDriverWait(self.driver, 10).until(find_input)
        except Exception:
            main_inputs = [
                i for i in self.driver.find_elements(By.CSS_SELECTOR, "main input:not([type='hidden'])")
                if i.is_displayed()
            ]
            target_input = main_inputs[0] if main_inputs else None

        assert target_input is not None, "게시판 검색창을 찾지 못했습니다."

        try:
            target_input.click()
        except Exception:
            pass
        target_input.send_keys(Keys.CONTROL, "a")
        target_input.send_keys(Keys.BACKSPACE)
        if keyword:
            target_input.send_keys(keyword)
        target_input.send_keys(Keys.RETURN)
        time.sleep(1)

    # ──────────────────────────────────────────────
    # 정렬
    # ──────────────────────────────────────────────

    def _open_sort_dropdown(self) -> WebElement:
        """정렬 토글 버튼을 클릭하여 정렬 옵션 드롭다운(MUI Popover)을 열고 해당 컨테이너 요소를 반환한다."""
        import time

        # 1. 이미 열려있는 팝오버가 있는지 확인
        open_popovers = [
            p for p in self.driver.find_elements(
                By.CSS_SELECTOR,
                "[role='menu'], [role='listbox'], .MuiMenu-paper, [class*='MuiPopover-paper']"
            )
            if p.is_displayed()
        ]
        if open_popovers:
            return open_popovers[-1]

        # 2. 정렬 버튼 찾기
        sort_btns = [
            b for b in self.driver.find_elements(
                By.XPATH,
                "//main//button[contains(., '최신') or contains(., '좋아요') or contains(., '정렬')] | //button[contains(., '최신순') or contains(., '좋아요순')]"
            )
            if b.is_displayed() and not any(k in b.text for k in ("글쓰기", "새 글", "검색"))
        ]
        assert sort_btns, "정렬 버튼을 찾지 못했습니다."
        btn = sort_btns[0]

        try:
            btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", btn)

        # 3. 팝오버가 나타날 때까지 대기
        def find_open_popover():
            for p in self.driver.find_elements(
                By.CSS_SELECTOR,
                "[role='menu'], [role='listbox'], .MuiMenu-paper, [class*='MuiPopover-paper'], [role='presentation'] [class*='paper']"
            ):
                if p.is_displayed():
                    return p
            return None

        popover = WebDriverWait(self.driver, 3).until(lambda _: find_open_popover())
        return popover

    def _click_sort_option(self, target_text: str) -> None:
        """정렬 팝오버 내부에서 지정된 옵션(예: '최신순', '좋아요순')을 정확히 클릭한다."""
        import time
        try:
            popover = self._open_sort_dropdown()
            # 팝오버 내부에서만 옵션 탐색
            options = popover.find_elements(
                By.XPATH,
                f".//*[self::li or @role='menuitem' or @role='option' or self::button or contains(@class, 'MenuItem') or self::div][contains(text(), '{target_text}')]"
            )
            clicked = False
            for opt in options:
                if opt.is_displayed() and opt.text.strip() == target_text:
                    try:
                        opt.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", opt)
                    clicked = True
                    break
            if not clicked and options:
                try:
                    options[0].click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", options[0])
                clicked = True
        except Exception:
            try:
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
                pass
        time.sleep(1)

    def sort_by_latest(self) -> None:
        """최신순 정렬을 선택한다."""
        self._click_sort_option("최신순")

    def sort_by_oldest(self) -> None:
        """좋아요순 정렬을 선택한다 (LXP UI에는 '최신순'과 '좋아요순'만 지원됨)."""
        self._click_sort_option("좋아요순")

    # ──────────────────────────────────────────────
    # 게시글 작성
    # ──────────────────────────────────────────────

    def click_write_button(self) -> None:
        """게시글 작성 버튼을 클릭한다."""
        import time
        from selenium.common.exceptions import StaleElementReferenceException

        for _ in range(6):
            try:
                write_btns = []
                for b in self.driver.find_elements(
                    By.XPATH,
                    "//button[contains(., '글쓰기')] | //a[contains(., '글쓰기')] | //*[@role='button'][contains(., '글쓰기')]",
                ):
                    try:
                        if b.is_displayed():
                            write_btns.append(b)
                    except StaleElementReferenceException:
                        continue

                if not write_btns:
                    try:
                        write_btns = role_elements(self.driver, "button", re.compile(r"글쓰기|write", re.I))
                    except StaleElementReferenceException:
                        time.sleep(0.5)
                        continue

                if write_btns:
                    target = write_btns[0]
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
                    except Exception:
                        pass
                    try:
                        target.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", target)

                try:
                    WebDriverWait(self.driver, 3).until(
                        lambda d: "write" in d.current_url or self.is_write_form_open()
                    )
                    return
                except Exception:
                    pass
            except StaleElementReferenceException:
                time.sleep(0.5)
                continue
            time.sleep(0.5)

    def fill_article_form(
        self,
        *,
        title: str,
        content: str,
        attachment_path: str | None = None,
        is_secret: bool = False,
    ) -> None:
        from selenium.webdriver.common.keys import Keys
        import time

        # 1. 글쓰기 폼의 제목 입력창(input[name='title'])이 뜰 때까지 대기
        title_input = WebDriverWait(self.driver, 10).until(
            lambda d: next(
                (
                    i for i in d.find_elements(By.CSS_SELECTOR, "input[name='title']")
                    if i.is_displayed()
                ),
                None
            )
        )
        assert title_input is not None, "글쓰기 제목 입력창을 찾지 못했습니다."

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
        time.sleep(0.5)

        # 2. 본문 에디터 대기 및 입력
        ed = WebDriverWait(self.driver, 10).until(
            lambda d: next(
                (
                    e for e in d.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
                    if e.is_displayed()
                ),
                None
            )
        )
        assert ed is not None, "본문 에디터를 찾지 못했습니다."
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ed)
        except Exception:
            pass
        ed.click()
        ed.send_keys(content)
        time.sleep(0.5)

        # 첨부파일
        if attachment_path:
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if file_inputs:
                file_inputs[0].send_keys(str(Path(attachment_path).resolve()))

        # 비밀글
        if is_secret:
            checkbox_candidates = [
                e for e in self.driver.find_elements(
                    By.XPATH,
                    "//label[contains(., '비밀')] | //*[contains(text(), '비밀')]/ancestor::label | //input[@type='checkbox'][contains(@name, 'secret') or contains(@id, 'secret')]"
                )
                if e.is_displayed()
            ]
            if not checkbox_candidates:
                checkbox_candidates = role_elements(self.driver, "checkbox", re.compile(r"비밀|secret|private", re.I))
            if checkbox_candidates:
                target = checkbox_candidates[0]
                inputs = target.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                is_checked = inputs[0].is_selected() if inputs else (target.get_attribute("aria-checked") == "true")
                if not is_checked:
                    click_when_ready(self.driver, target)
                    time.sleep(0.5)

    def submit_article_form(self) -> None:
        """게시글 저장/등록 버튼을 클릭한다."""
        import time

        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        btns = [
            b
            for b in self.driver.find_elements(
                By.XPATH,
                "//button[contains(., '저장')] | //button[contains(., '등록')] | //button[contains(., '작성')] | //input[@type='submit']"
            )
            if b.is_displayed() and b.tag_name.lower() not in ("body", "html", "main")
        ]
        if not btns:
            btns = [
                b
                for b in self.driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
                if any(k in (b.text or "") for k in ("저장", "등록", "작성", "완료", "submit"))
                and b.is_displayed()
            ]
        if not btns:
            btns = role_elements(self.driver, "button", re.compile(r"저장|등록|작성|완료|submit", re.I))

        assert btns, "게시글 저장/등록 버튼을 찾지 못했습니다."
        target_btn = btns[-1]
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_btn)
        except Exception:
            pass
        try:
            WebDriverWait(self.driver, 5).until(lambda d: target_btn.is_enabled())
        except Exception:
            pass
        time.sleep(0.5)
        try:
            target_btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", target_btn)
        time.sleep(2)

    def cancel_article_form(self) -> None:
        """게시글 작성/수정 폼의 취소 버튼을 클릭한다."""
        import time
        for _ in range(3):
            try:
                btns = [
                    b for b in self.driver.find_elements(
                        By.XPATH, "//button[contains(., '취소')] | //button[contains(@class, 'cancel')]"
                    ) if b.is_displayed()
                ]
                if not btns:
                    btns = role_elements(self.driver, "button", re.compile(r"취소|cancel", re.I))
                if btns:
                    click_when_ready(self.driver, btns[0])
                    time.sleep(1)
                    return
            except Exception:
                pass
            time.sleep(0.5)

    # ──────────────────────────────────────────────
    # 게시글 수정·삭제
    # ──────────────────────────────────────────────

    def click_back_to_list(self) -> None:
        """게시글 상세에서 '글 목록' 버튼을 클릭한다."""
        import time

        btns = [
            b
            for b in self.driver.find_elements(
                By.XPATH, "//button[contains(., '글 목록')] | //a[contains(., '글 목록')]"
            )
            if b.is_displayed()
        ]
        if btns:
            try:
                btns[0].click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", btns[0])
        else:
            self.app.open_classroom_section("articles")
        time.sleep(1)
        self.wait_until_loaded()

    def click_delete_article(self) -> None:
        """게시글 상세에서 삭제 버튼을 클릭한다 (더보기 메뉴 열림 대응)."""
        import time

        # 1. 더보기(⋮) 버튼 탐색
        more_btn = WebDriverWait(self.driver, 10).until(
            lambda d: next(
                (
                    b for b in d.find_elements(
                        By.CSS_SELECTOR,
                        "button[id='menu-button'], button[aria-label='more'], button:has(svg[data-testid='MoreVertIcon'])"
                    )
                    if b.is_displayed()
                ),
                None
            )
        )
        assert more_btn is not None, "게시글 더보기(⋮) 버튼을 찾지 못했습니다."

        # 더보기 클릭 (클릭 후 menuitem이 뜰 때까지 재시도)
        for _ in range(3):
            try:
                more_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", more_btn)
            time.sleep(0.5)
            menu_items = self.driver.find_elements(
                By.XPATH,
                "//*[@role='menuitem'][contains(., '삭제')] | //li[contains(., '삭제')]"
            )
            if any(m.is_displayed() for m in menu_items):
                break

        # 2. 메뉴에서 '삭제' 항목 대기 및 클릭
        del_item = WebDriverWait(self.driver, 5).until(
            lambda d: next(
                (
                    m for m in d.find_elements(
                        By.XPATH,
                        "//*[@role='menuitem'][contains(., '삭제')] | //li[contains(., '삭제')]"
                    )
                    if m.is_displayed()
                ),
                None
            )
        )
        assert del_item is not None, "게시글 삭제 메뉴 아이템을 찾지 못했습니다."

        try:
            del_item.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", del_item)
        time.sleep(0.5)

    def confirm_delete(self) -> None:
        """삭제 확인 다이얼로그에서 확인/삭제 버튼을 클릭한다."""
        import time

        def find_confirm_btn(d):
            dialogs = d.find_elements(By.XPATH, "//*[@role='dialog']")
            for dlg in dialogs:
                if dlg.is_displayed():
                    for b in dlg.find_elements(By.TAG_NAME, "button"):
                        txt = b.text.strip()
                        cls = b.get_attribute("class") or ""
                        if b.is_displayed() and ("삭제" in txt or "containedError" in cls):
                            if "취소" not in txt:
                                return b
            return None

        confirm_btn = WebDriverWait(self.driver, 8).until(find_confirm_btn)
        assert confirm_btn is not None, "삭제 확인 다이얼로그의 확인/삭제 버튼을 찾지 못했습니다."

        try:
            confirm_btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", confirm_btn)

        # 다이얼로그가 사라지거나 상세 URL에서 벗어날 때까지 대기
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: not bool(re.search(r"/articles/\d+$", d.current_url))
            )
        except Exception:
            pass
        time.sleep(1)

    def cancel_delete(self) -> None:
        """삭제 확인 다이얼로그에서 취소 버튼을 클릭한다."""
        btns = role_elements(self.driver, "button", re.compile(r"취소|cancel", re.I))
        if btns:
            click_when_ready(self.driver, btns[0])

    # ──────────────────────────────────────────────
    # 게시글 상세 확인
    # ──────────────────────────────────────────────

    def get_detail_title(self) -> str:
        """게시글 상세 화면의 제목 텍스트를 반환한다."""
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: bool(re.search(r"/articles/\d+(?:[/?#]|$)", d.current_url))
                and not re.search(r"/articles/\d+/(?:edit|modify)(?:[/?#]|$)", d.current_url, re.I)
            )
        except TimeoutException:
            pass

        excluded = (
            "게시판", "공지사항", "자유게시판", "질문과 답변", "Q&A",
            "글쓰기", "최종프로젝트", "QA6_1팀", "QA6", "파일 선택", "드래그앤"
        )
        def visible_title(d):
            for sel in ("main h1", "main h2", "main h3", "main h4", "h1", "h2", "h3", "h4", "main [class*='title' i]"):
                for el in d.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        txt = el.text.strip()
                        if txt and not any(ex in txt for ex in excluded):
                            return txt
            return False

        try:
            return WebDriverWait(self.driver, 10).until(visible_title)
        except TimeoutException:
            pass
        try:
            heading = wait_role(self.driver, self.driver, "heading", timeout=3)
            txt = heading.text.strip()
            if txt and not any(ex in txt for ex in excluded):
                return txt
        except Exception:
            pass
        return ""

    def get_detail_content(self) -> str:
        """게시글 상세 화면의 본문 텍스트를 반환한다."""
        # 헤더나 네비게이션이 아닌 main 영역 내부의 실제 본문 탐색
        article_body = self.driver.find_elements(
            By.CSS_SELECTOR,
            "main article, main [data-testid*='content'], main [class*='ArticleContent'], main [class*='Viewer'], main [class*='viewer']"
        )
        for el in article_body:
            if el.is_displayed() and el.text.strip():
                return el.text.strip()

        content_els = self.driver.find_elements(
            By.CSS_SELECTOR,
            "main [class*='content'], main [class*='body'], main p"
        )
        for e in content_els:
            text = e.text.strip()
            if e.is_displayed() and len(text) > 2 and text not in ("검색", "글 목록", "맨 위로"):
                return text
        try:
            return self.driver.find_element(By.CSS_SELECTOR, "main").text.strip()
        except Exception:
            return ""

    def has_attachment(self) -> bool:
        """게시글 상세에 첨부파일 링크 또는 영역이 표시되는지 확인한다."""
        candidates = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[class*='attach'], [class*='file'], a[download], [aria-label*='첨부']"
        )
        return any(e.is_displayed() for e in candidates)

    def go_back_to_list(self) -> None:
        """게시글 상세에서 목록으로 돌아간다."""
        back_btns = role_elements(self.driver, "button", re.compile(r"목록|뒤로|back|list", re.I))
        if back_btns and back_btns[0].is_displayed():
            click_when_ready(self.driver, back_btns[0])
        else:
            self.driver.back()
        self.wait_until_loaded()

    # ──────────────────────────────────────────────
    # 댓글
    # ──────────────────────────────────────────────

    def write_comment(self, content: str) -> None:
        """댓글 입력창에 내용을 입력하고 등록한다."""
        comment_inputs = self.driver.find_elements(
            By.CSS_SELECTOR,
            "textarea[placeholder*='댓글'], [aria-label*='댓글'], "
            "[placeholder*='댓글']"
        )
        if not comment_inputs:
            comment_inputs = role_elements(self.driver, "textbox",
                                           re.compile(r"댓글|comment", re.I))

        assert comment_inputs, "댓글 입력창을 찾지 못했습니다."
        visible = [e for e in comment_inputs if e.is_displayed()]
        assert visible, "댓글 입력창이 표시되지 않습니다."

        visible[0].clear()
        visible[0].send_keys(content)

        # 등록 버튼 클릭
        submit_btns = role_elements(self.driver, "button",
                                    re.compile(r"등록|작성|저장|submit", re.I))
        if submit_btns:
            click_when_ready(self.driver, submit_btns[-1])

    def is_comment_visible(self, content: str) -> bool:
        """특정 내용의 댓글이 화면에 표시되는지 확인한다."""
        matches = text_elements(self.driver, content, exact=False)
        return any(e.is_displayed() for e in matches)

    def delete_comment(self, content: str) -> None:
        """특정 내용의 댓글을 찾아 삭제한다."""
        comment_el = wait_text(self.driver, self.driver, content, exact=False)
        # 댓글 요소 내부 또는 인근에 있는 삭제 버튼 클릭
        parent = comment_el.find_element(By.XPATH, "./ancestor::*[contains(@class,'comment') or contains(@class,'reply')][1]")
        del_btns = role_elements(parent, "button", re.compile(r"삭제|delete", re.I))
        if del_btns:
            click_when_ready(self.driver, del_btns[0])
            self.confirm_delete()

    # ──────────────────────────────────────────────
    # 권한 확인
    # ──────────────────────────────────────────────

    def is_article_form_open(self) -> bool:
        """게시글 작성/수정 폼(또는 모달/페이지)이 열려 있는지 확인한다."""
        if "write" in self.driver.current_url:
            return True
        # 목록 화면의 '제목 검색' 입력창은 제외
        title_inputs = [
            i for i in self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[name='title'], [data-testid*='title'], form input[placeholder*='제목'], [role='dialog'] input[placeholder*='제목']"
            )
            if i.is_displayed() and "검색" not in (i.get_attribute("placeholder") or "")
        ]
        if title_inputs:
            return True

        dialogs = self.driver.find_elements(By.CSS_SELECTOR, "[role='dialog'], form, [class*='Modal']")
        for d in dialogs:
            try:
                if d.is_displayed():
                    cancels = d.find_elements(By.XPATH, ".//button[contains(., '취소')]")
                    saves = d.find_elements(By.XPATH, ".//button[contains(., '저장') or contains(., '등록') or contains(., '게시')]")
                    if cancels and saves:
                        return True
            except Exception:
                continue
        return False

    def is_write_button_visible(self) -> bool:
        """게시글 작성 버튼이 화면에 있는지 확인한다."""
        btns = role_elements(self.driver, "button",
                             re.compile(r"글쓰기|작성|새 글|write|create", re.I))
        return any(b.is_displayed() for b in btns)

    def visible_text(self) -> str:
        """현재 게시판 화면의 표시 텍스트를 반환한다."""
        body = self.driver.find_element(By.TAG_NAME, "body").text.strip()
        assert body, "게시판 화면의 본문이 비어 있습니다."
        return body

    def expect_home_data_visible(self, home_widget_text: str) -> None:
        """클래스 홈 게시판 위젯의 게시글이 전체 목록에도 표시되는지 검증한다."""
        candidates = [
            line.strip()
            for line in home_widget_text.splitlines()
            if len(line.strip()) >= 2 and not line.strip().startswith("20")
        ]
        assert candidates, "홈 게시판 위젯에서 비교 가능한 게시글 제목을 찾지 못했습니다."
        page_text = WebDriverWait(self.driver, self.LOAD_TIMEOUT).until(
            lambda driver: (
                text if any(candidate in text for candidate in candidates) else False
            )
            if (text := driver.find_element(By.TAG_NAME, "body").text.strip())
            else False,
            message="홈 게시판 기준 글이 게시판 목록에 로드되지 않았습니다.",
        )
        assert any(candidate in page_text for candidate in candidates), (
            "홈 게시판 위젯과 게시판 목록에서 같은 게시글을 찾지 못했습니다. "
            f"기준값: {candidates}"
        )

    def expect_learner_management_hidden(self) -> None:
        """수강생 화면에 게시판 관리 기능이 노출되지 않는지 검증한다."""
        page_text = self.visible_text()
        visible = [text for text in self.MANAGEMENT_TEXTS if text in page_text]
        assert not visible, f"수강생 게시판에 관리자 기능이 노출됐습니다: {visible}"

    # ──────────────────────────────────────────────
    # 글쓰기 폼 UI 탐색 헬퍼
    # ──────────────────────────────────────────────

    def is_write_form_open(self) -> bool:
        """글쓰기 폼(제목 입력창)이 현재 화면에 열려 있는지 확인한다."""
        try:
            WebDriverWait(self.driver, 5).until(
                lambda d: "write" in d.current_url or any(
                    i.is_displayed()
                    for i in d.find_elements(By.CSS_SELECTOR, "input[name='title']")
                )
            )
            return True
        except Exception:
            return False

    def get_title_input_maxlength(self) -> int | None:
        """글쓰기 폼의 제목 입력창 maxlength 속성 값을 반환한다. 없으면 None."""
        try:
            title_input = WebDriverWait(self.driver, 5).until(
                lambda d: next(
                    (
                        i for i in d.find_elements(By.CSS_SELECTOR, "input[name='title']")
                        if i.is_displayed()
                    ),
                    None,
                )
            )
            if title_input is None:
                return None
            val = title_input.get_attribute("maxlength")
            return int(val) if val else None
        except Exception:
            return None

    def is_attachment_ui_visible(self) -> bool:
        """글쓰기 폼에 파일 첨부 UI(input[type='file'] 또는 첨부 버튼)가 존재하는지 확인한다."""
        # input[type='file'] 은 display:none 일 수 있으므로 존재 여부만 확인
        file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if file_inputs:
            return True
        # 첨부 버튼/영역 텍스트 검색
        attach_els = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '파일') or contains(normalize-space(.), '첨부') "
            "or contains(normalize-space(.), 'attach') or contains(normalize-space(.), 'upload')]",
        )
        return any(e.is_displayed() for e in attach_els)

    def is_course_dropdown_visible(self) -> bool:
        """글쓰기 폼에 연결 과목 드롭다운/셀렉트 UI가 존재하는지 확인한다."""
        selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
        for s in selects:
            if s.is_displayed():
                return True
        # role='combobox' 또는 '과목' 텍스트가 포함된 버튼/셀렉트 찾기
        comboboxes = role_elements(self.driver, "combobox", re.compile(r".", re.S))
        if any(c.is_displayed() for c in comboboxes):
            return True
        course_labels = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '연결 과목') or contains(normalize-space(.), '과목 선택')]",
        )
        return any(e.is_displayed() for e in course_labels)

    # ──────────────────────────────────────────────
    # 상세 페이지 메타정보 헬퍼
    # ──────────────────────────────────────────────

    def get_detail_author(self) -> str:
        """게시글 상세 화면의 작성자 텍스트를 반환한다."""
        # 1. time 태그의 부모 영역 내에서 작성자 span/div 찾기
        time_tags = self.driver.find_elements(By.TAG_NAME, "time")
        for t in time_tags:
            try:
                parent = t.find_element(By.XPATH, "./..")
                for span in parent.find_elements(By.XPATH, ".//span | .//p | .//div"):
                    txt = span.text.strip()
                    if txt and txt != t.text.strip() and len(txt) < 30 and not any(kw in txt for kw in ("좋아요", "댓글", "목록")):
                        return txt
            except Exception:
                continue

        # 2. CSS 및 XPath 검색
        candidates = self.driver.find_elements(
            By.CSS_SELECTOR,
            "main span[class*='Typography'], [class*='author'], [class*='writer'], [class*='user']",
        )
        for el in candidates:
            try:
                if el.is_displayed():
                    txt = el.text.strip()
                    if txt and not any(kw in txt for kw in ("좋아요", "댓글", "목록", "저장", "수정", "삭제")) and len(txt) < 30:
                        return txt
            except Exception:
                continue
        return ""

    def get_detail_date(self) -> str:
        """게시글 상세 화면의 작성일 텍스트를 반환한다."""
        # 1. <time> 태그 우선 검색
        time_tags = self.driver.find_elements(By.TAG_NAME, "time")
        for t in time_tags:
            try:
                txt = t.text.strip()
                if txt:
                    return txt
            except Exception:
                continue

        # 2. 날짜 패턴 텍스트 검색 (예: '분 전', '시간 전', '일 전', '202')
        candidates = self.driver.find_elements(
            By.XPATH,
            "//main//*[contains(text(), '전') or contains(text(), '202') or contains(text(), ':')]",
        )
        for el in candidates:
            try:
                if el.is_displayed():
                    txt = el.text.strip()
                    if any(s in txt for s in ("분 전", "시간 전", "일 전", "초 전")) or re.search(r"\d{4}[.-]\d{2}", txt):
                        return txt
            except Exception:
                continue
        return ""

    def is_like_button_visible(self) -> bool:
        """게시글 상세 화면에 좋아요(추천/Like) 버튼/아이콘이 존재하는지 확인한다."""
        like_btns = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '좋아요') or contains(normalize-space(.), '추천') "
            "or contains(@aria-label, 'like') or contains(@aria-label, '좋아요')]",
        )
        if any(e.is_displayed() for e in like_btns):
            return True
        # SVG 아이콘 기반 탐지 (thumb-up 등)
        like_icons = self.driver.find_elements(
            By.CSS_SELECTOR,
            "svg[data-testid*='thumb'], svg[data-testid*='like'], svg[data-testid*='heart'], "
            "button[aria-label*='like' i], button[aria-label*='좋아요']",
        )
        return any(e.is_displayed() for e in like_icons)

    def is_comment_section_visible(self) -> bool:
        """게시글 상세 화면에 댓글 입력창 또는 댓글 컨테이너가 존재하는지 확인한다."""
        comment_inputs = self.driver.find_elements(
            By.CSS_SELECTOR,
            "textarea[placeholder*='댓글'], textarea[placeholder*='comment'], "
            "[aria-label*='댓글'], [aria-label*='comment']",
        )
        if any(e.is_displayed() for e in comment_inputs):
            return True
        comment_sections = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[class*='comment'], [class*='reply'], [id*='comment']",
        )
        return any(e.is_displayed() for e in comment_sections)

    def get_empty_search_message(self) -> str:
        """검색 결과 없음 안내 문구를 반환한다. 없으면 빈 문자열."""
        candidates = self.driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(.), '검색 결과가 없') or "
            "contains(normalize-space(.), '게시글이 없') or "
            "contains(normalize-space(.), 'no result') or "
            "contains(normalize-space(.), '찾을 수 없')]",
        )
        for el in candidates:
            if el.is_displayed():
                return el.text.strip()
        return ""

    # ──────────────────────────────────────────────
    # 좋아요 클릭 및 수량
    # ──────────────────────────────────────────────

    def _find_like_button_element(self) -> WebElement | None:
        """좋아요 클릭 가능한 버튼/아이콘 요소를 반환한다."""
        # 1. aria-label 기반
        for sel in (
            "button[aria-label*='좋아요']",
            "button[aria-label*='like' i]",
        ):
            for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return el
        # 2. SVG 아이콘의 상위 button
        for sel in (
            "svg[data-testid*='thumb']",
            "svg[data-testid*='like']",
            "svg[data-testid*='heart']",
        ):
            for icon in self.driver.find_elements(By.CSS_SELECTOR, sel):
                if icon.is_displayed():
                    btn = self.driver.execute_script(
                        "return arguments[0].closest('button, [role=\"button\"]');",
                        icon,
                    )
                    if btn:
                        return btn
        # 3. 텍스트 기반
        for el in self.driver.find_elements(
            By.XPATH,
            "//*[self::button or @role='button']"
            "[contains(normalize-space(.), '좋아요') or contains(normalize-space(.), '추천')]",
        ):
            if el.is_displayed():
                return el
        return None

    def click_like_button(self) -> None:
        """게시글 상세에서 좋아요 버튼을 클릭한다."""
        btn = WebDriverWait(self.driver, 10).until(
            lambda d: self._find_like_button_element(),
            message="좋아요 버튼을 찾지 못했습니다.",
        )
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", btn
            )
        except Exception:
            pass
        click_when_ready(self.driver, btn)

    def get_like_count(self) -> int:
        """게시글 상세에서 현재 좋아요 수를 반환한다."""
        btn = self._find_like_button_element()
        if btn is None:
            return 0
        # 버튼 또는 인접 요소에서 숫자 추출
        text = btn.text.strip()
        m = re.search(r"(\d+)", text)
        if m:
            return int(m.group(1))
        # 인접 span 탐색
        siblings = btn.find_elements(By.XPATH, "./following-sibling::*[1] | ./preceding-sibling::*[1]")
        for sib in siblings:
            m = re.search(r"(\d+)", sib.text.strip())
            if m:
                return int(m.group(1))
        return 0

    # ──────────────────────────────────────────────
    # 게시글 수정
    # ──────────────────────────────────────────────

    def edit_article(self, *, new_title: str | None = None, new_content: str | None = None) -> None:
        """게시글 상세에서 수정 버튼을 눌러 제목/본문을 변경하고 저장한다.
        상세 화면에 진입한 상태에서 호출해야 한다."""
        import time
        from selenium.webdriver.common.keys import Keys

        # 1. 더보기(⋮) → 수정 메뉴
        more_btn = WebDriverWait(self.driver, 10).until(
            lambda d: next(
                (
                    b for b in d.find_elements(
                        By.CSS_SELECTOR,
                        "button[id='menu-button'], button[aria-label='more'], "
                        "button:has(svg[data-testid='MoreVertIcon'])",
                    )
                    if b.is_displayed()
                ),
                None,
            )
        )
        if more_btn:
            click_when_ready(self.driver, more_btn)
            time.sleep(0.5)

        edit_item = WebDriverWait(self.driver, 5).until(
            lambda d: next(
                (
                    m for m in d.find_elements(
                        By.XPATH,
                        "//*[@role='menuitem'][contains(., '수정')] | //li[contains(., '수정')]",
                    )
                    if m.is_displayed()
                ),
                None,
            )
        )
        assert edit_item is not None, "게시글 수정 메뉴 아이템을 찾지 못했습니다."
        click_when_ready(self.driver, edit_item)
        time.sleep(1)

        # 2. 수정 폼 로드 대기
        WebDriverWait(self.driver, 10).until(
            lambda d: "write" in d.current_url or self.is_write_form_open()
        )

        # 3. 제목 변경
        if new_title:
            title_input = WebDriverWait(self.driver, 10).until(
                lambda d: next(
                    (
                        i for i in d.find_elements(By.CSS_SELECTOR, "input[name='title']")
                        if i.is_displayed()
                    ),
                    None,
                )
            )
            if title_input:
                title_input.send_keys(Keys.CONTROL, "a")
                title_input.send_keys(Keys.BACKSPACE)
                title_input.send_keys(new_title)

        # 4. 본문 변경
        if new_content:
            ed = next(
                (e for e in self.driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']") if e.is_displayed()),
                None,
            )
            if ed:
                ed.click()
                ed.send_keys(Keys.CONTROL, "a")
                ed.send_keys(Keys.BACKSPACE)
                ed.send_keys(new_content)

        # 5. 저장
        self.submit_article_form()
        self.wait_until_loaded()

    # ──────────────────────────────────────────────
    # 편의 메서드
    # ──────────────────────────────────────────────

    @staticmethod
    def make_qa_title(prefix: str = "게시글") -> str:
        """테스트마다 고유한 [QA-AUTO] 게시글 제목을 생성한다."""
        return f"[QA-AUTO] {prefix}-{uuid.uuid4().hex[:8]}"
