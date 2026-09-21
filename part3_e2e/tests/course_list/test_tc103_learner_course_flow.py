"""TC103 수강생 학습과목 기본 흐름 E2E."""

import pytest

from part3_e2e.config import CourseTestData
from part3_e2e.pages.course_list_page import CourseListPage


@pytest.mark.e2e
@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.course_list
def test_tc103_learner_course_list_detail_and_tabs(
    learner_course_list_page: CourseListPage,
    course_test_data: CourseTestData,
) -> None:
    """수강생이 SANDBOX 과목 목록·상세·탭을 확인하고 목록으로 복귀한다."""
    course_list = learner_course_list_page
    course_name = course_test_data.course_name

    course_list.open()
    course_list.expect_course_once(course_name)
    course_list.expect_course_thumbnail(course_name)

    detail = course_list.open_course(course_name)
    detail.expect_lesson_visible(course_test_data.test_lecture_name)

    for tab_name in (
        detail.PROGRESS_TAB,
        detail.MAP_TAB,
        detail.INTRODUCTION_TAB,
        detail.LESSONS_TAB,
    ):
        detail.select_tab(tab_name)

    selected_before_back = detail.selected_tab_name()
    detail.app.go_back()
    detail.expect_tab_not_selected(selected_before_back)
    selected_after_back = detail.selected_tab_name()

    detail.app.reload()
    detail.expect_loaded()
    detail.expect_tab_selected(selected_after_back)

    course_list.open()
    course_list.expect_loaded()
    course_list.expect_course_once(course_name)
