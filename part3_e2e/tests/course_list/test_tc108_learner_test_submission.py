"""TC108 TEST 응시 결과의 학습 현황·학습맵 반영 E2E."""

import pytest

from part3_e2e.config import CourseTestData
from part3_e2e.pages.course_list_page import CourseListPage


@pytest.mark.e2e
@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.course_list
def test_tc108_test_result_updates_progress_and_learning_map(
    learner_course_list_page: CourseListPage,
    course_test_data: CourseTestData,
) -> None:
    """TEST 제출 결과가 학습 현황과 해당 학습맵 노드에 반영된다."""
    course_list = learner_course_list_page
    lesson_name = course_test_data.test_lecture_name

    course_list.open()
    detail = course_list.open_course(course_test_data.course_name)

    # 제출 전 TEST 행과 TEST 노드 상태를 기준값으로 저장한다.
    progress_before = detail.progress_row_text(lesson_name)
    test_node_before = detail.map_node_signature(lesson_name)

    # 수업 목록에서 TEST에 응시하고 첫 문항을 제출한다.
    detail.select_tab(detail.LESSONS_TAB)
    attempt = detail.start_test(lesson_name)
    attempt.answer_first_question(course_test_data.test_answer)
    attempt.submit()
    attempt.expect_result()
    assert attempt.result_text().strip()

    # 과목 상세로 돌아와 제출 결과가 두 화면에 각각 반영됐는지 확인한다.
    detail.page.back()
    detail.expect_loaded()
    detail.expect_progress_changed(lesson_name, progress_before)
    detail.expect_map_node_changed(lesson_name, test_node_before)
