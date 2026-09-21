"""TC110 로그아웃·직접 URL 접근 차단·재로그인 E2E."""

import pytest
from selenium.webdriver.common.by import By

from part3_e2e.config import CourseTestData, Credentials
from part3_e2e.pages.course_list_page import CourseListPage
from part3_e2e.pages.login_page import LoginPage


@pytest.mark.e2e
@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.boundary
@pytest.mark.course_list
def test_tc110_logout_blocks_detail_and_relogin_restores_access(
    learner_course_list_page: CourseListPage,
    course_test_data: CourseTestData,
    learner_credentials: Credentials,
) -> None:
    """로그아웃 상태의 과목 상세 접근을 차단하고 재로그인 후 복구한다."""
    course_list = learner_course_list_page
    course_name = course_test_data.course_name

    # 로그인 상태에서 수강 중인 과목과 TEST 수업을 정상 조회한다.
    course_list.open()
    course_list.expect_course_once(course_name)
    detail = course_list.open_course(course_name)
    detail.expect_lesson_visible(course_test_data.test_lecture_name)
    detail_url = detail.page.current_url

    login_page = LoginPage(detail.page, detail.app.settings)
    login_page.logout_and_wait()

    # 로그아웃 후 과목 상세 URL에 직접 접근하면 로그인 화면으로 이동한다.
    detail.page.get(detail_url)
    login_page.expect_login_required()
    assert course_name not in detail.page.find_element(By.TAG_NAME, "body").text

    # 동일한 수강생으로 재로그인하면 원래 과목 상세 접근과 학습 상태가 복구된다.
    login_page.open_full_login_form()
    login_page.login(learner_credentials)
    login_page.wait_until_logged_in()
    detail.expect_loaded()
    detail.expect_lesson_visible(course_test_data.test_lecture_name)

    course_list.open()
    course_list.expect_course_once(course_name)
