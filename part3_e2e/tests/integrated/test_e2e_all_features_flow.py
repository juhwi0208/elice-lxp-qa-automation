"""전체 기능(E2E 통합) 탭의 단일 사용자 여정.

현재 자동화된 공통·조회·권한 구간을 한 브라우저 세션에서 순서대로 실행한다.
데이터를 생성하는 과목 설정·시험 제출·일정 CRUD·게시글 CRUD는 각각의 cleanup이
확정된 뒤 이 흐름의 변이 구간으로 연결한다.
"""

from __future__ import annotations

import allure
import pytest
from selenium.webdriver.common.by import By

from part3_e2e.config import CourseTestData, Credentials
from part3_e2e.pages.board_page import BoardPage
from part3_e2e.pages.classroom_home_page import ClassroomHomePage
from part3_e2e.pages.course_detail_page import CourseDetailPage
from part3_e2e.pages.course_list_page import CourseListPage
from part3_e2e.pages.course_management_page import CourseManagementPage
from part3_e2e.pages.login_page import LoginPage
from part3_e2e.pages.schedule_page import SchedulePage


@allure.epic("전체 기능 E2E 통합")
@allure.feature("클래스 홈 → 학습 과목 → 수업 일정 → 게시판 → 인증 경계")
@pytest.mark.e2e
@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.educator
@pytest.mark.integrated
def test_e2e_all_01_read_only_journey_and_authentication_recovery(
    learner_classroom_home: ClassroomHomePage,
    learner_schedule_page: SchedulePage,
    learner_board_page: BoardPage,
    educator_app_shell,
    course_test_data: CourseTestData,
    learner_credentials: Credentials,
) -> None:
    """E2E-ALL-01의 조회·UI 권한·로그아웃·재인증 구간을 한 번에 검증한다."""
    home = learner_classroom_home
    learner_app = home.app
    course_list = CourseListPage(learner_app)

    with allure.step("1~3. 수강생 로그인 상태로 클래스 홈 기준값 저장·새로고침"):
        home.open()
        home_url = home.driver.current_url
        baseline = home.snapshots()
        home.expect_widget_contains(home.COURSE_WIDGET, course_test_data.course_name)

        home.app.reload()
        home.expect_loaded()
        home.expect_snapshots(baseline)

    with allure.step("4~5, 17~20. 학습 과목 목록·상세·탭·TEST 접근 확인"):
        course_list.open()
        course_list.expect_course_once(course_test_data.course_name)
        course_list.expect_course_thumbnail(course_test_data.course_name)

        detail: CourseDetailPage = course_list.open_course(course_test_data.course_name)
        detail_url = detail.driver.current_url
        detail.expect_lesson_visible(course_test_data.test_lecture_name)
        for tab_name in (
            detail.PROGRESS_TAB,
            detail.MAP_TAB,
            detail.INTRODUCTION_TAB,
            detail.LESSONS_TAB,
        ):
            detail.select_tab(tab_name)
            detail.expect_tab_selected(tab_name)
        detail.expect_test_start_available(course_test_data.test_lecture_name)

        course_list.open()
        course_list.expect_course_once(course_test_data.course_name)
        course_list.expect_management_controls_hidden()

    with allure.step("6, 38~42, 45. 홈 일정 기준값과 전체 일정 화면·수강생 권한 비교"):
        home.open()
        schedule_baseline = baseline[home.SCHEDULE_WIDGET]
        learner_schedule_page.open()
        schedule_url = learner_schedule_page.driver.current_url
        learner_schedule_page.expect_home_data_visible(schedule_baseline.text)
        learner_schedule_page.expect_learner_management_hidden()

        learner_schedule_page.driver.refresh()
        learner_schedule_page.expect_loaded()
        learner_schedule_page.expect_home_data_visible(schedule_baseline.text)

    with allure.step("7~8, 46. 홈 게시판 기준값과 게시판 목록·수강생 권한 비교"):
        home.open()
        board_baseline = baseline[home.BOARD_WIDGET]
        learner_board_page.open()
        board_url = learner_board_page.driver.current_url
        learner_board_page.expect_home_data_visible(board_baseline.text)
        learner_board_page.expect_learner_management_hidden()

    with allure.step("12, 37. 교육자 세션의 과목·일정 관리 진입점 확인"):
        management = CourseManagementPage(educator_app_shell)
        management.open()
        management.expect_loaded()

        educator_schedule = SchedulePage(educator_app_shell)
        educator_schedule.open()
        educator_schedule.visible_text()

    protected_urls = (home_url, detail_url, schedule_url, board_url)
    login_page = LoginPage(home.driver, home.app.settings)

    with allure.step("59~60. 로그아웃 후 네 기능 직접 URL 접근 차단 확인"):
        login_page.logout_and_wait()
        for protected_url in protected_urls:
            home.driver.get(protected_url)
            login_page.expect_login_required()
            body_text = home.driver.find_element(By.TAG_NAME, "body").text
            assert course_test_data.course_name not in body_text, (
                "로그아웃 상태에서 보호된 학습 데이터가 로그인 화면에 노출됐습니다."
            )

    with allure.step("61~62. 동일 수강생 재로그인 후 전체 기능·초기 기준값 복구 확인"):
        login_page.open_full_login_form()
        login_page.login(learner_credentials)
        login_page.wait_until_logged_in()

        home.open()
        home.expect_snapshots(baseline)
        course_list.open()
        course_list.expect_course_once(course_test_data.course_name)
        learner_schedule_page.open()
        learner_schedule_page.expect_home_data_visible(schedule_baseline.text)
        learner_board_page.open()
        learner_board_page.expect_home_data_visible(board_baseline.text)
