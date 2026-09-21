"""클래스 홈, 학습 과목, 수업 일정, 게시판이 공유하는 Selenium 메뉴."""

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from part3_e2e.config import ClassroomContext, E2ESettings
from part3_e2e.pages.common.base_page import BasePage
from part3_e2e.pages.common.selenium_support import role_elements, wait_role


class AppShell(BasePage):
    def __init__(
        self,
        driver: WebDriver,
        settings: E2ESettings,
        classroom: ClassroomContext,
    ) -> None:
        super().__init__(driver, settings)
        self.classroom = classroom
        self.content = driver

    @property
    def classroom_path(self) -> str:
        return f"/classrooms/{self.classroom.classroom_id}"

    def ensure_sidebar_open(self) -> None:
        """사이드바(좌측 메뉴)가 닫혀있다면 상단 햄버거 메뉴(barsIcon)를 클릭해 펼친다."""
        import time
        from selenium.webdriver.common.by import By

        # 1. 메뉴 링크 중 하나라도 이미 화면에 보이는지 확인
        menu_items = self.driver.find_elements(
            By.XPATH,
            "//*[contains(text(), '학습 과목') or contains(text(), '수업 일정') or contains(text(), '게시판') or contains(text(), '클래스 홈')]",
        )
        if any(item.is_displayed() for item in menu_items):
            return  # 이미 사이드바가 열려 있음

        # 2. 닫혀 있다면 상단 햄버거(선 3개 barsIcon) 버튼을 찾아 클릭
        bars_buttons = self.driver.find_elements(
            By.XPATH,
            "//button[descendant::*[@data-icon='bars' or @data-testid='barsIcon']]",
        )
        for btn in bars_buttons:
            try:
                if btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    break
            except Exception:
                continue

    def is_on_classroom_home(self) -> bool:
        from urllib.parse import urlparse
        current_path = urlparse(self.driver.current_url).path.rstrip("/")
        expected_path = self.classroom_path.rstrip("/")
        return current_path == expected_path

    def open_classroom(self) -> None:
        import time
        from selenium.webdriver.common.by import By

        if self.is_on_classroom_home():
            return

        time.sleep(0.5)
        # 1. 사이드바가 있으면 사이드바 내의 '클래스 홈' 링크 클릭 시도
        self.ensure_sidebar_open()
        home_links = self.driver.find_elements(
            By.XPATH,
            "//a[contains(., '클래스 홈')] | //*[@role='link'][contains(., '클래스 홈')]",
        )
        for l in home_links:
            try:
                if l.is_displayed() and l.tag_name.lower() not in ("body", "html"):
                    self.driver.execute_script("arguments[0].click();", l)
                    time.sleep(1.5)
                    if self.is_on_classroom_home():
                        return
            except Exception:
                continue

        # 2. LXP 화면에서 강의실 카드/링크 클릭 시도
        links = self.driver.find_elements(
            By.XPATH,
            f"//*[contains(text(), 'QA6_1팀') or (contains(text(), '1팀') and contains(text(), '최종프로젝트')) or contains(@href, '{self.classroom.classroom_id}')]",
        )
        for l in links:
            try:
                if l.is_displayed() and l.tag_name.lower() not in ("body", "html"):
                    self.driver.execute_script("arguments[0].click();", l)
                    time.sleep(1.5)
                    if self.is_on_classroom_home():
                        return
            except Exception:
                continue

        # 3. fallback: 직접 URL 이동
        self.open(self.classroom_path)
        time.sleep(2)


    def open_classroom_section(self, section: str) -> None:
        import time
        from urllib.parse import urlparse
        from selenium.webdriver.common.by import By

        normalized_section = section.strip("/")
        if not normalized_section or "/" in normalized_section:
            raise ValueError("강의실 섹션은 한 단계 경로여야 합니다.")

        target_path = f"{self.classroom_path}/{normalized_section}".rstrip("/")

        section_names = {
            "courses": "학습 과목",
            "schedules": "수업 일정",
            "articles": "게시판",
        }

        # URL만 맞고 SPA 본문이 비었거나 오류 화면인 경우에는 다시 로드한다.
        current_path = urlparse(self.driver.current_url).path.rstrip("/")
        if current_path == target_path:
            expected_text = section_names.get(normalized_section, "")
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if expected_text and expected_text in body_text and "존재하지 않는 클래스" not in body_text:
                return
            self.open(f"{self.classroom_path}/{normalized_section}")
            time.sleep(1.5)

        if "accounts/signin" in self.driver.current_url:
            from part3_e2e.config import load_credentials
            from part3_e2e.pages.login_page import LoginPage
            try:
                creds = load_credentials("LEARNER")
                LoginPage(self.driver, self.settings).login(creds)
                time.sleep(2)
            except Exception:
                pass

        # 1. 상세 페이지에 있을 때 '과목 목록' 등 상단 뒤로가기 링크 클릭 시도
        if normalized_section == "courses" and "courses/" in self.driver.current_url:
            back_links = self.driver.find_elements(
                By.XPATH,
                "//a[contains(., '과목 목록')] | //button[contains(., '과목 목록')] | //*[contains(text(), '과목 목록')]",
            )
            for bl in back_links:
                try:
                    if bl.is_displayed():
                        self.driver.execute_script("arguments[0].click();", bl)
                        time.sleep(1.5)
                        if urlparse(self.driver.current_url).path.rstrip("/") == target_path:
                            return
                except Exception:
                    continue

        # 2. 사이드바 메뉴 클릭 시도
        name = section_names.get(normalized_section)
        clicked = False
        if name:
            self.ensure_sidebar_open()
            for _ in range(2):
                menu_items = self.driver.find_elements(
                    By.XPATH,
                    f"//a[contains(., '{name}')] | //button[contains(., '{name}')] | //*[@role='link'][contains(., '{name}')] | //*[@role='button'][contains(., '{name}')] | //*[contains(@class, 'ListItem')][contains(., '{name}')]",
                )
                for item in menu_items:
                    if item.is_displayed() and item.tag_name.lower() not in ("body", "html"):
                        try:
                            self.driver.execute_script("arguments[0].click();", item)
                            time.sleep(1.5)
                            if urlparse(self.driver.current_url).path.rstrip("/") == target_path:
                                clicked = True
                                break
                        except Exception:
                            continue
                if clicked or urlparse(self.driver.current_url).path.rstrip("/") == target_path:
                    break
                time.sleep(0.5)

        # 3. fallback: 직접 URL 이동
        if urlparse(self.driver.current_url).path.rstrip("/") != target_path:
            self.open(f"{self.classroom_path}/{normalized_section}")
            time.sleep(1.5)


    def menu(self, name: str) -> WebElement:
        self.ensure_sidebar_open()
        matches = role_elements(self.driver, "link", name)
        assert len(matches) == 1, f"{name!r} 메뉴는 정확히 하나여야 합니다."
        return matches[0]

    def select_menu(self, name: str) -> None:
        """사이드바 메뉴 링크를 클릭하거나, 실패 시 URL 직접 이동으로 폴백한다."""
        import time
        from selenium.common.exceptions import TimeoutException

        self.ensure_sidebar_open()
        try:
            wait_role(self.driver, self.driver, "link", name).click()
            time.sleep(0.5)
        except TimeoutException:
            # 사이드바 링크를 찾지 못한 경우: 메뉴 이름으로 섹션 경로를 추론하여 직접 이동
            _menu_to_section = {
                "학습 과목": "courses",
                "수업 일정": "schedules",
                "게시판": "articles",
                "클래스 홈": "",
            }
            section = _menu_to_section.get(name)
            if section is not None:
                self.open_classroom_section(section) if section else self.open_classroom()
            else:
                raise

    def expect_menu_visible(self, name: str) -> None:
        self.ensure_sidebar_open()
        wait_role(self.driver, self.driver, "link", name)

