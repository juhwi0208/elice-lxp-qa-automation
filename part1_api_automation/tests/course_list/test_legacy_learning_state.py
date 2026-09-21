"""TC82~85 퀴즈·TEST 응시·과목 완료 상태 조회 테스트."""

from __future__ import annotations

import pytest

from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import assert_api_success


def _skip_when_test_not_readable(response) -> None:
    """학습자 TEST 상태 때문에 자료를 읽을 수 없으면 사전조건 미충족 처리한다."""
    if not response.ok:
        return
    try:
        body = response.json()
    except ValueError:
        return
    fail_code = body.get("fail_code")
    if fail_code == "ready_test_admission_status":
        pytest.skip("학습자 TEST 시작 전 상태(Ready): 시험 시작 후 실행해야 합니다.")
    if fail_code == "not_accessible_test":
        pytest.skip(
            "학습자 TEST 완료 상태(Completed): 재응시 가능 상태로 전환한 뒤 "
            "실행해야 합니다."
        )


def _assert_page(body: dict, count_key: str, items_key: str, limit: int) -> list[dict]:
    total = body.get(count_key)
    items = body.get(items_key)
    assert isinstance(total, int) and total >= 0
    assert isinstance(items, list)
    assert len(items) <= limit
    assert total >= len(items)
    assert all(isinstance(item, dict) for item in items)
    return items


@pytest.mark.read_only
@pytest.mark.learner
def test_tc082_learner_gets_material_quiz_detail(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
    material_quiz_id: int,
) -> None:
    """TC82: 로그인한 학습자 본인의 퀴즈 문제 정보를 반환한다."""
    response = legacy_course_api.get_material_quiz(material_quiz_id, learner_headers)
    _skip_when_test_not_readable(response)
    body = assert_api_success(response, expected_api_status_code=200)

    quiz = body.get("material_quiz")
    assert isinstance(quiz, dict)
    assert quiz.get("id") == material_quiz_id
    assert isinstance(quiz.get("question_title"), str)
    assert "answer_info" in quiz
    assert quiz.get("groups") is None or isinstance(quiz.get("groups"), list)
    options = quiz.get("options")
    assert isinstance(options, list) and options
    assert all(isinstance(option, dict) for option in options)


@pytest.mark.read_only
@pytest.mark.learner
def test_tc083_learner_lists_material_quiz_responses(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
    material_quiz_id: int,
) -> None:
    """TC83: 퀴즈 응답 목록 구조를 반환하며 정답은 노출하지 않는다."""
    count = 20
    response = legacy_course_api.list_material_quiz_responses(
        material_quiz_id,
        None,
        learner_headers,
        offset=0,
        count=count,
    )
    _skip_when_test_not_readable(response)
    body = assert_api_success(response, expected_api_status_code=200)
    responses = _assert_page(body, "quiz_response_count", "quiz_responses", count)

    assert all(isinstance(item.get("id"), int) for item in responses)
    assert all(isinstance(item.get("user_id"), int) for item in responses)
    assert all(item.get("answer") is None for item in responses)


@pytest.mark.read_only
@pytest.mark.educator
def test_tc084_educator_lists_learner_test_admissions(
    legacy_course_api: LegacyCourseApi,
    educator_headers: dict,
    learner_user_id: int,
    lecture_id: int,
) -> None:
    """TC84: TA 이상 권한으로 대상 학습자의 TEST 응시 이력을 반환한다."""
    count = 20
    response = legacy_course_api.list_test_admissions(
        learner_user_id,
        lecture_id,
        educator_headers,
        offset=0,
        count=count,
    )
    body = assert_api_success(response, expected_api_status_code=200)
    admissions = _assert_page(
        body,
        "test_admission_count",
        "test_admissions",
        count,
    )

    assert all(
        item.get("lecture_id", lecture_id) == lecture_id
        and item.get("user_id", learner_user_id) == learner_user_id
        for item in admissions
    )


@pytest.mark.read_only
@pytest.mark.learner
def test_tc085_learner_lists_course_completion_statuses(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
    learner_user_id: int,
    course_id: int,
) -> None:
    """TC85: 대상 사용자의 과목 완료 상태 목록을 반환한다."""
    count = 20
    response = legacy_course_api.list_course_completion_statuses(
        course_id,
        learner_user_id,
        learner_headers,
        offset=0,
        count=count,
    )
    body = assert_api_success(response, expected_api_status_code=200)
    statuses = _assert_page(
        body,
        "course_completion_status_count",
        "course_completion_status_list",
        count,
    )

    assert all(
        item.get("course_id", course_id) == course_id
        and item.get("user_id", learner_user_id) == learner_user_id
        for item in statuses
    )
