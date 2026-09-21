"""TC76 기존 통합 API 학습과목 목록 조회 테스트."""

import pytest

from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import assert_api_success


@pytest.mark.read_only
@pytest.mark.learner
def test_tc076_learner_lists_legacy_courses(
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
) -> None:
    """TC76: 요청 범위에 맞는 과목 목록과 전체 개수가 반환된다."""
    offset = 0
    count = 20
    response = legacy_course_api.list_courses(
        learner_headers,
        offset=offset,
        count=count,
    )
    body = assert_api_success(response, expected_api_status_code=200)

    assert isinstance(body.get("course_count"), int)
    assert body["course_count"] >= 0
    assert isinstance(body.get("courses"), list)
    assert len(body["courses"]) <= count
    assert all(isinstance(course, dict) for course in body["courses"])
