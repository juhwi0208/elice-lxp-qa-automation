"""학습과목 E2E 전용 fixture."""

import pytest

from part3_e2e.config import CourseTestData, load_course_test_data
from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.course_management_page import CourseManagementPage
from part3_e2e.pages.course_list_page import CourseListPage


@pytest.fixture(scope="session")
def course_test_data() -> CourseTestData:
    return load_course_test_data()


@pytest.fixture
def educator_course_management_page(
    educator_app_shell: AppShell,
) -> CourseManagementPage:
    return CourseManagementPage(educator_app_shell)


@pytest.fixture
def learner_course_list_page(learner_app_shell: AppShell) -> CourseListPage:
    return CourseListPage(learner_app_shell)
