"""Elice 계정 Selenium 로그인 화면 Page Object."""

from __future__ import annotations

import re
from urllib.parse import urlencode

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from part3_e2e.config import Credentials, E2ESettings
from part3_e2e.pages.common.selenium_support import (
    role_elements,
    wait_role,
    wait_url,
    wait_visible,
)


def build_login_url(settings: E2ESettings) -> str:
    continue_to = f"{settings.web_base_url}/lxp"
    query = urlencode(
        {"continue_to": continue_to, "org": settings.org_name_short, "lang": "ko"}
    )
    return f"{settings.accounts_base_url}/accounts/signin/me?{query}"


def build_logout_url(settings: E2ESettings) -> str:
    continue_to = f"{settings.web_base_url}/lxp"
    query = urlencode(
        {"continue_to": continue_to, "org": settings.org_name_short, "lang": "ko"}
    )
    return f"{settings.accounts_base_url}/accounts/signout/me?{query}"


class LoginPage:
    def __init__(self, driver: WebDriver, settings: E2ESettings) -> None:
        self.driver = driver
        self.page = driver
        self.settings = settings

    @property
    def email_input(self) -> WebElement:
        return wait_visible(
            self.driver,
            (By.CSS_SELECTOR, "input[type='email'], [placeholder='이메일'], [placeholder='Email'], input[name='email']"),
        )

    @property
    def password_input(self) -> WebElement:
        return wait_visible(
            self.driver,
            (By.CSS_SELECTOR, "input[type='password'], [placeholder='비밀번호'], [placeholder='Password'], input[name='password']"),
        )

    @property
    def login_button(self) -> WebElement:
        btns = [
            b
            for b in self.driver.find_elements(
                By.XPATH,
                "//button[contains(., '로그인')] | //button[contains(., 'Login')] | //button[contains(., 'Sign in')]"
            )
            if b.is_displayed()
        ]
        if btns:
            return btns[0]
        return wait_role(self.driver, self.driver, "button", re.compile(r"로그인|Login|Sign in", re.I))

    @property
    def login_url(self) -> str:
        return build_login_url(self.settings)

    @property
    def logout_url(self) -> str:
        return build_logout_url(self.settings)

    def open(self) -> None:
        self.driver.get(self.login_url)
        try:
            self.open_full_login_form()
        except Exception:
            pass

    def login(self, credentials: Credentials) -> None:
        import time
        from selenium.webdriver.common.keys import Keys

        # 1. 이메일 입력 (존재 시 대기 후 입력)
        email_el = None
        try:
            email_el = WebDriverWait(self.driver, 4).until(
                lambda d: next(
                    (
                        e for e in d.find_elements(
                            By.CSS_SELECTOR,
                            "input[type='email'], [placeholder='이메일'], [placeholder='Email'], input[name='email']"
                        )
                        if e.is_displayed()
                    ),
                    None
                )
            )
        except TimeoutException:
            pass

        if email_el is not None:
            try:
                email_el.send_keys(Keys.CONTROL, "a")
                email_el.send_keys(Keys.BACKSPACE)
            except Exception:
                pass
            email_el.send_keys(credentials.email)
            try:
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
                    "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                    email_el,
                )
            except Exception:
                pass
            time.sleep(0.3)

        # 2. 비밀번호 입력
        pw_input = self.password_input
        try:
            pw_input.send_keys(Keys.CONTROL, "a")
            pw_input.send_keys(Keys.BACKSPACE)
        except Exception:
            pass
        pw_input.send_keys(credentials.password)
        time.sleep(0.5)

        # 3. React onChange 이벤트 디스패치 및 버튼 활성화 유도
        try:
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
                "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                pw_input,
            )
        except Exception:
            pass

        if not self.login_button.is_enabled():
            pw_input.send_keys(" ")
            pw_input.send_keys(Keys.BACKSPACE)
            time.sleep(0.5)

        # 4. 로그인 버튼 클릭 또는 엔터 전송
        try:
            if self.login_button.is_enabled():
                self.login_button.click()
            else:
                pw_input.send_keys(Keys.RETURN)
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", self.login_button)
            except Exception:
                pw_input.send_keys(Keys.RETURN)

        # 5. 로그인 후 LXP나 클래스로 전환될 때까지 대기
        try:
            WebDriverWait(self.driver, 15).until(
                lambda d: (
                    "accounts/signin" not in d.current_url
                    or any(
                        elem.is_displayed()
                        for elem in d.find_elements(
                            By.CSS_SELECTOR,
                            "[class*='Header'], [class*='Nav'], [class*='Lxp'], [class*='Sidebar'], [class*='Classroom'], [role='main']",
                        )
                    )
                )
            )
        except TimeoutException:
            pass

    def expect_login_required(self) -> None:
        expected_url = re.compile(
            rf"^(?:{re.escape(self.settings.accounts_base_url)}|{re.escape(self.settings.web_base_url)})"
            r"/accounts/signin(?:/(?:me|history))?(?:[?#].*)?$"
        )
        def login_surface_ready(driver) -> bool:
            return bool(expected_url.match(driver.current_url))

        WebDriverWait(self.driver, 30).until(login_surface_ready)
        assert any(k in self.driver.current_url for k in ("signin", "login", "accounts"))

    def open_full_login_form(self) -> None:
        email_inputs = self.driver.find_elements(
            By.CSS_SELECTOR,
            "input[type='email'], [placeholder='이메일'], [placeholder='Email']"
        )
        if email_inputs and email_inputs[0].is_displayed():
            return

        switch_candidates = self.driver.find_elements(
            By.XPATH,
            "//a[contains(., '다른 계정')] | //button[contains(., '다른 계정')] | //*[contains(text(), '다른 계정')] | "
            "//a[contains(., 'different account')] | //button[contains(., 'different account')] | "
            "//a[contains(., '기록 삭제')] | //a[contains(., 'Remove history')]",
        )
        for cand in switch_candidates:
            if cand.is_displayed():
                try:
                    self.driver.execute_script("arguments[0].click();", cand)
                    break
                except Exception:
                    continue

        try:
            WebDriverWait(self.driver, 5).until(
                lambda d: any(
                    inp.is_displayed()
                    for inp in d.find_elements(
                        By.CSS_SELECTOR,
                        "input[type='email'], [placeholder='이메일'], [placeholder='Email']"
                    )
                )
            )
            return
        except TimeoutException:
            pass

        # 여전히 이메일 입력창이 없으면 쿠키/스토리지 클리어 후 재진입
        try:
            self.driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
            self.driver.delete_all_cookies()
            self.driver.get(self.login_url)
            wait_visible(
                self.driver,
                (By.CSS_SELECTOR, "input[type='email'], [placeholder='이메일'], [placeholder='Email']"),
                timeout=5
            )
        except Exception:
            pass

    def logout_and_wait(self) -> None:
        self.driver.get(self.logout_url)
        wait_url(self.driver, f"{self.settings.web_base_url}/lxp")
        self.driver.execute_script(
            "window.localStorage.clear(); window.sessionStorage.clear();"
        )
        self.driver.delete_all_cookies()

        # Selenium 쿠키 삭제는 현재 도메인에만 적용되므로 계정 도메인도 정리한다.
        self.driver.get(self.settings.accounts_base_url)
        self.driver.execute_script(
            "window.localStorage.clear(); window.sessionStorage.clear();"
        )
        self.driver.delete_all_cookies()
        self.driver.get("about:blank")

    def wait_until_logged_in(self) -> None:
        expected_url = re.compile(
            rf"^{re.escape(self.settings.web_base_url)}(?:[/?#].*)?$"
        )
        wait_url(self.driver, expected_url)

    def login_and_wait(self, credentials: Credentials) -> None:
        self.open()
        self.login(credentials)
        self.wait_until_logged_in()
