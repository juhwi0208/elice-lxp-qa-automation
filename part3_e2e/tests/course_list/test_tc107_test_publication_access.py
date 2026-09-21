"""TC107 관리자 TEST 공개 상태와 수강생 접근 정책 연동 E2E."""

import pytest

from part3_e2e.config import CourseTestData
from part3_e2e.pages.course_list_page import CourseListPage
from part3_e2e.pages.course_management_page import CourseManagementPage


@pytest.mark.e2e
@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.educator
@pytest.mark.course_list
def test_tc107_test_publication_controls_learner_access_and_restores_state(
    educator_course_management_page: CourseManagementPage,
    learner_course_list_page: CourseListPage,
    course_test_data: CourseTestData,
) -> None:
    """TEST 공개 상태 변경이 수강생에게 반영되고 원래 값으로 복원된다."""
    management = educator_course_management_page
    learner_courses = learner_course_list_page
    course_name = course_test_data.course_name
    lesson_name = course_test_data.test_lecture_name

    management.open()
    management.open_course(course_name)
    original_state = management.publication_state(lesson_name)
    changed_state = not original_state

    try:
        management.set_publication_state(lesson_name, changed_state)
        management.expect_publication_state(lesson_name, changed_state)

        learner_courses.open()
        detail = learner_courses.open_course(course_name)
        detail.page.refresh()
        detail.expect_loaded()
        detail.expect_test_access_state(lesson_name, changed_state)
    finally:
        management.open()
        management.open_course(course_name)
        management.set_publication_state(lesson_name, original_state)
        management.expect_publication_state(lesson_name, original_state)

    learner_courses.open()
    restored_detail = learner_courses.open_course(course_name)
    restored_detail.page.refresh()
    restored_detail.expect_loaded()
    restored_detail.expect_test_access_state(lesson_name, original_state)
