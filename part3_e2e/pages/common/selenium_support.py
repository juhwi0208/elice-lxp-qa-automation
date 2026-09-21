"""Selenium Page Object에서 공유하는 명시적 대기와 접근성 탐색 도구."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Pattern

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


SearchContext = WebDriver | WebElement
DEFAULT_TIMEOUT = 20


def click_when_ready(
    driver: WebDriver,
    target: WebElement | Callable[[], WebElement],
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """SPA 알림·전환 애니메이션이 사라질 때까지 클릭을 재시도한다."""
    def click(_driver: WebDriver) -> bool:
        element = target() if callable(target) else target
        if not element.is_displayed():
            return False
        
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
                element,
            )
            element.click()
            return True
        except (ElementClickInterceptedException, StaleElementReferenceException, ElementNotInteractableException):
            try:
                driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                return False

    WebDriverWait(driver, timeout).until(click)


def xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


def wait_visible(
    driver: WebDriver,
    locator: tuple[str, str],
    timeout: int = DEFAULT_TIMEOUT,
) -> WebElement:
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))


def wait_url(
    driver: WebDriver,
    expected: str | Pattern[str],
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    def matches(current: WebDriver) -> bool:
        if isinstance(expected, str):
            return expected.rstrip("/") in current.current_url
        return bool(expected.search(current.current_url))

    WebDriverWait(driver, timeout).until(matches)
    return driver.current_url


def _role_xpath(role: str) -> str:
    native = {
        "button": "self::button",
        "link": "self::a[@href]",
        "heading": "self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6",
        "textbox": "self::input[not(@type) or @type='text' or @type='email' or @type='password'] or self::textarea",
        "checkbox": "self::input[@type='checkbox']",
        "radio": "self::input[@type='radio']",
    }.get(role)
    conditions = [f"@role='{role}'"]
    if native:
        conditions.append(native)
    return ".//*[" + " or ".join(conditions) + "]"


def accessible_name(element: WebElement) -> str:
    return (
        element.get_attribute("aria-label")
        or element.get_attribute("value")
        or element.text
        or ""
    ).strip()


def role_elements(
    scope: SearchContext,
    role: str,
    name: str | Pattern[str] | None = None,
) -> list[WebElement]:
    elements = scope.find_elements(By.XPATH, _role_xpath(role))
    if name is None:
        return elements
    if isinstance(name, str):
        return [element for element in elements if accessible_name(element) == name]
    return [element for element in elements if name.search(accessible_name(element))]


def wait_role(
    driver: WebDriver,
    scope: SearchContext,
    role: str,
    name: str | Pattern[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> WebElement:
    def find(_driver: WebDriver) -> WebElement | bool:
        try:
            for element in role_elements(scope, role, name):
                if element.is_displayed():
                    return element
        except StaleElementReferenceException:
            return False
        return False

    return WebDriverWait(driver, timeout).until(find)


def text_elements(
    scope: SearchContext,
    text: str | Pattern[str],
    *,
    exact: bool = True,
) -> list[WebElement]:
    if isinstance(text, Pattern):
        script = """
            var pattern = new RegExp(arguments[0], arguments[1]);
            var root = arguments[2] || document;
            var elements = root.querySelectorAll('*');
            var matches = [];
            for (var i = 0; i < elements.length; i++) {
                var el = elements[i];
                var style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                if (el.offsetWidth === 0 && el.offsetHeight === 0) continue;
                
                var ariaLabel = el.getAttribute('aria-label') || '';
                var textContent = el.innerText || el.textContent || '';
                var isMatch = pattern.test(textContent) || (ariaLabel && pattern.test(ariaLabel));
                
                if (isMatch) {
                    var hasMatchingVisibleChild = false;
                    for (var j = 0; j < el.children.length; j++) {
                        var child = el.children[j];
                        var cStyle = window.getComputedStyle(child);
                        if (cStyle.display === 'none' || cStyle.visibility === 'hidden' || cStyle.opacity === '0') continue;
                        if (child.offsetWidth === 0 && child.offsetHeight === 0) continue;
                        var childText = child.innerText || child.textContent || '';
                        var childAria = child.getAttribute('aria-label') || '';
                        if (pattern.test(childText) || (childAria && pattern.test(childAria))) {
                            hasMatchingVisibleChild = true;
                            break;
                        }
                    }
                    if (!hasMatchingVisibleChild) {
                        matches.push(el);
                    }
                }
            }
            return matches;
        """
        flags = ""
        if text.flags & re.I:
            flags += "i"
            
        script_args = [text.pattern, flags]
        if isinstance(scope, WebElement):
            script_args.append(scope)
        else:
            script_args.append(None)
            
        driver = scope if isinstance(scope, WebDriver) else scope.parent
        elements = driver.execute_script(script, *script_args)
        return elements
        
    if exact:
        literal = xpath_literal(text)
        xpath = (
            f".//*[normalize-space(.)={literal} and "
            f"not(.//*[normalize-space(.)={literal}])]"
        )
    else:
        xpath = f".//*[contains(normalize-space(.), {xpath_literal(text)})]"
    return scope.find_elements(By.XPATH, xpath)


def wait_text(
    driver: WebDriver,
    scope: SearchContext,
    text: str | Pattern[str],
    *,
    exact: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
) -> WebElement:
    def find(_driver: WebDriver) -> WebElement | bool:
        try:
            for element in text_elements(scope, text, exact=exact):
                if element.is_displayed():
                    return element
        except StaleElementReferenceException:
            return False
        return False

    return WebDriverWait(driver, timeout).until(find)
