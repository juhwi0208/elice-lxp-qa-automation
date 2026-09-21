"""로그인 이후 여러 기능 탭이 공유하는 LXP 앱 fixture."""

from __future__ import annotations

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from part3_e2e.config import (
    ClassroomContext,
    CourseTestData,
    E2EConfigurationError,
    E2ESettings,
    load_classroom_context,
    load_course_test_data,
)
from part3_e2e.pages.board_page import BoardPage
from part3_e2e.pages.classroom_home_page import ClassroomHomePage
from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.schedule_page import SchedulePage


@pytest.fixture(scope="session")
def classroom_context() -> ClassroomContext:
    """모든 강의실 기능이 공유하는 QA 강의실 식별자를 제공한다."""
    try:
        return load_classroom_context()
    except E2EConfigurationError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def course_test_data() -> CourseTestData:
    """기능별·통합 E2E가 같은 학습과목 기준값을 공유한다."""
    return load_course_test_data()


@pytest.fixture(scope="session")
def learner_app_shell(
    learner_authenticated_driver: WebDriver,
    e2e_settings: E2ESettings,
    classroom_context: ClassroomContext,
) -> AppShell:
    """학습자 로그인 상태와 공통 메뉴 동작이 결합된 앱 객체."""
    return AppShell(learner_authenticated_driver, e2e_settings, classroom_context)


@pytest.fixture(scope="session")
def educator_app_shell(
    educator_authenticated_driver: WebDriver,
    e2e_settings: E2ESettings,
    classroom_context: ClassroomContext,
) -> AppShell:
    """교육자 로그인 상태와 공통 메뉴 동작이 결합된 앱 객체."""
    return AppShell(educator_authenticated_driver, e2e_settings, classroom_context)


@pytest.fixture
def learner_classroom_home(learner_app_shell: AppShell) -> ClassroomHomePage:
    return ClassroomHomePage(learner_app_shell)


@pytest.fixture
def learner_schedule_page(learner_app_shell: AppShell) -> SchedulePage:
    return SchedulePage(learner_app_shell)


@pytest.fixture
def learner_board_page(learner_app_shell: AppShell) -> BoardPage:
    return BoardPage(learner_app_shell)
