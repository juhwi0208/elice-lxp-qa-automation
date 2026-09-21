"""TC100·TC101 기존 통합 API 권한·인증 경계 테스트."""

import pytest

from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import (
    assert_error_response,
    logic_error,
)


def _assert_no_sensitive_quiz_data(body: dict) -> None:
    for key in (
        "material_quiz",
        "quiz_questions",
        "questions",
        "answers",
        "quiz_responses",
        "user_response",
    ):
        assert not body.get(key), f"미인증 응답에 {key} 정보가 노출됐습니다."


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.boundary
def test_tc100_learner_cannot_read_private_course(
    legacy_course_api: LegacyCourseApi,
    private_course_id: int,
    learner_headers: dict,
) -> None:
    """TC100: 조회 권한이 없는 비공개 과목의 상세 데이터가 노출되지 않는다."""
    response = legacy_course_api.get_course(private_course_id, learner_headers)
    body = assert_error_response(
        response,
        logic_error(409, error_code="insufficient_permission"),
    )

    assert not body.get("course")
    assert not body.get("lectures")
    assert not body.get("lecture_pages")


@pytest.mark.read_only
@pytest.mark.boundary
def test_tc101_unauthenticated_quiz_request_is_rejected(
    legacy_course_api: LegacyCourseApi,
    org_name_short: str,
    material_quiz_id: int,
) -> None:
    """TC101: 인증 헤더가 없으면 퀴즈 문제·정답·응답이 노출되지 않는다."""
    response = legacy_course_api.get_material_quiz(
        material_quiz_id,
        {"x-elice-org-name-short": org_name_short},
    )

    body = assert_error_response(
        response,
        logic_error(403, error_code="not_found_sessionkey"),
    )

    _assert_no_sensitive_quiz_data(body)
