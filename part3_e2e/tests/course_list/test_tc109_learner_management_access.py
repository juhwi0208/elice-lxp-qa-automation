"""TC109 수강생 관리자 학습 과목 화면 접근 차단 E2E."""

import pytest

from part3_e2e.config import CourseTestData
from part3_e2e.pages.course_list_page import CourseListPage


@pytest.mark.e2e
@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.boundary
@pytest.mark.course_list
def test_tc109_learner_cannot_use_course_management(
    learner_course_list_page: CourseListPage,
    course_test_data: CourseTestData,
) -> None:
    """수강생은 허용된 과목만 조회하고 관리자 관리 기능은 사용할 수 없다."""
    course_list = learner_course_list_page
    course_name = course_test_data.course_name

    # 수강생에게 허용된 학습 과목 목록과 상세 화면은 정상 조회된다.
    course_list.open()
    course_list.expect_course_once(course_name)
    course_list.expect_course_thumbnail(course_name)

    detail = course_list.open_course(course_name)
    detail.expect_lesson_visible(course_test_data.test_lecture_name)

    # 상세 화면에서 돌아온 뒤에도 기존 수강 과목은 변경 없이 유지된다.
    detail.app.go_back()
    if "courses/" in detail.driver.current_url:
        course_list.open()
    course_list.expect_loaded()
    course_list.expect_course_once(course_name)


    # 관리자와 동일한 학습 과목 URL에 직접 접근해도 관리 기능은 노출되지 않는다.
    course_list.open()
    course_list.expect_management_controls_hidden()
    course_list.expect_course_once(course_name)
    course_list.expect_course_thumbnail(course_name)
