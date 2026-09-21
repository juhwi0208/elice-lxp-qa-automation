"""TC93~95·98~99 학습과목 입력 검증 및 존재하지 않는 리소스 테스트."""

from __future__ import annotations

import pytest

from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import assert_error_response, logic_error


def _assert_fields_absent(body: dict, *field_names: str) -> None:
    """오류 응답이 요청 대상 데이터를 함께 노출하지 않는지 확인한다."""
    for field_name in field_names:
        assert not body.get(field_name), (
            f"오류 응답에 {field_name!r} 데이터가 노출됐습니다."
        )


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.boundary
def test_tc093_track_id_is_required(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
) -> None:
    """TC93: track/get 요청에서 track_id가 누락되면 정확히 400 논리 오류다."""
    response = legacy_course_api.get_track(None, learner_headers)

    body = assert_error_response(response, logic_error(400))

    _assert_fields_absent(body, "track", "courses")


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.boundary
def test_tc094_course_list_offset_is_required(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
) -> None:
    """TC94: course/list 요청에서 offset이 누락되면 정확히 400 논리 오류다."""
    response = legacy_course_api.list_courses(
        learner_headers,
        offset=None,
        count=20,
    )

    body = assert_error_response(response, logic_error(400))

    _assert_fields_absent(body, "course_count", "courses")


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.boundary
def test_tc095_course_list_count_is_required(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
) -> None:
    """TC95: course/list 요청에서 count가 누락되면 정확히 400 논리 오류다."""
    response = legacy_course_api.list_courses(
        learner_headers,
        offset=0,
        count=None,
    )

    body = assert_error_response(response, logic_error(400))

    _assert_fields_absent(body, "course_count", "courses")


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.boundary
def test_tc098_missing_lecture_page_is_rejected(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
) -> None:
    """TC98: 존재하지 않는 수업 자료 조회는 정확히 409 논리 오류다."""
    response = legacy_course_api.get_lecture_page(2_147_483_647, learner_headers)

    body = assert_error_response(
        response,
        logic_error(409, error_code="lecture_page_not_found"),
    )

    _assert_fields_absent(body, "lecture_page", "material", "material_quiz")


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.boundary
def test_tc099_missing_material_quiz_is_rejected(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
) -> None:
    """TC99: 존재하지 않는 퀴즈 조회는 정확히 409 논리 오류다."""
    response = legacy_course_api.get_material_quiz(2_147_483_647, learner_headers)

    body = assert_error_response(
        response,
        logic_error(409, error_code="not_found_lecture_page"),
    )

    _assert_fields_absent(
        body,
        "material_quiz",
        "quiz_questions",
        "questions",
        "answers",
        "quiz_responses",
    )
