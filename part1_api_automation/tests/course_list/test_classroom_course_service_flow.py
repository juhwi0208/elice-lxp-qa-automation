"""현재 Classroom API의 학습과목 목록 계약을 검증한다."""

from __future__ import annotations

import pytest


@pytest.mark.read_only
@pytest.mark.learner
def test_learner_gets_unique_classroom_course(
    classroom_courses: list[dict],
    sandbox_course: dict,
    course_name: str,
    course_id: int,
) -> None:
    """현재 강의실 과목 목록에 설정한 QA 과목이 중복 없이 노출된다."""
    required_fields = {
        "id",
        "course_id",
        "title",
        "short_description",
        "image_file_url",
        "status",
    }

    assert classroom_courses
    assert sandbox_course["course_id"] == course_id
    assert sandbox_course["title"] == course_name
    assert not required_fields - sandbox_course.keys()
