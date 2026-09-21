"""TC75·77·78·79 기존 통합 API 학습과목 조회 테스트."""

from __future__ import annotations

import pytest

from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import assert_api_success


@pytest.mark.read_only
@pytest.mark.learner
def test_tc075_learner_gets_track_courses(
    legacy_course_api: LegacyCourseApi,
    track_id: int,
    learner_headers: dict,
) -> None:
    """TC75: track/get이 강의실 과목 목록과 순서를 반환한다."""
    response = legacy_course_api.get_track(track_id, learner_headers)
    body = assert_api_success(response, expected_api_status_code=200)

    track = body.get("track")
    assert isinstance(track, dict)
    assert track.get("id") == track_id

    courses = track.get("courses")
    assert isinstance(courses, list)
    assert all(isinstance(course, dict) for course in courses)


@pytest.mark.read_only
@pytest.mark.learner
def test_tc077_learner_gets_course_detail(
    legacy_course_api: LegacyCourseApi,
    course_id: int,
    learner_headers: dict,
) -> None:
    """TC77: course/get이 요청한 과목의 상세 정보를 반환한다."""
    response = legacy_course_api.get_course(course_id, learner_headers)
    body = assert_api_success(response, expected_api_status_code=200)

    course = body.get("course")
    assert isinstance(course, dict)
    assert course.get("id") == course_id
    assert isinstance(course.get("title"), str) and course["title"].strip()
    assert "status" in course or "is_opened" in course


@pytest.mark.read_only
@pytest.mark.learner
def test_tc078_learner_lists_course_lectures(
    legacy_course_api: LegacyCourseApi,
    course_id: int,
    learner_headers: dict,
    test_lecture_name: str,
) -> None:
    """TC78: lecture/list가 대상 과목의 수업 목록과 개수를 반환한다."""
    count = 20
    response = legacy_course_api.list_lectures(
        course_id,
        learner_headers,
        offset=0,
        count=count,
    )
    body = assert_api_success(response, expected_api_status_code=200)

    lecture_count = body.get("lecture_count")
    lectures = body.get("lectures")
    assert isinstance(lecture_count, int) and lecture_count >= 0
    assert isinstance(lectures, list)
    assert len(lectures) <= count
    assert lecture_count >= len(lectures)
    assert all(isinstance(lecture, dict) for lecture in lectures)
    lecture_ids = [lecture.get("id") for lecture in lectures]
    assert all(isinstance(lecture_id, int) for lecture_id in lecture_ids)
    assert len(lecture_ids) == len(set(lecture_ids)), "수업 목록에 중복 ID가 있습니다."
    assert any(
        lecture.get("title") == test_lecture_name for lecture in lectures
    ), f"대상 과목의 {test_lecture_name!r} 수업이 목록에 없습니다."


@pytest.mark.read_only
@pytest.mark.learner
def test_tc079_learner_gets_lecture_detail(
    legacy_course_api: LegacyCourseApi,
    lecture_id: int,
    learner_headers: dict,
) -> None:
    """TC79: lecture/get이 요청한 수업의 상세 정보를 반환한다."""
    response = legacy_course_api.get_lecture(lecture_id, learner_headers)
    body = assert_api_success(response, expected_api_status_code=200)

    lecture = body.get("lecture")
    assert isinstance(lecture, dict)
    assert lecture.get("id") == lecture_id
    assert isinstance(lecture.get("title"), str) and lecture["title"].strip()
    assert isinstance(lecture.get("is_opened"), bool)
