"""TC96·97·102 학습과목 변경 API 입력·권한 경계 테스트."""

from __future__ import annotations

import pytest

from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import (
    assert_api_success,
    assert_error_response,
    logic_error,
)
from test_support.cleanup import CleanupRegistry


def _track_courses(
    api: LegacyCourseApi,
    track_id: int,
    headers: dict,
) -> list[dict]:
    body = assert_api_success(
        api.get_track(track_id, headers),
        expected_api_status_code=200,
    )
    track = body.get("track")
    assert isinstance(track, dict)
    courses = track.get("courses")
    assert isinstance(courses, list)
    return courses


@pytest.mark.mutating
@pytest.mark.educator
@pytest.mark.boundary
def test_tc096_track_course_add_requires_course_id(
    allow_course_mutations: None,
    educator_headers: dict,
    legacy_course_api: LegacyCourseApi,
    track_id: int,
) -> None:
    """TC96: course_id 누락 요청은 거부되고 트랙 과목은 바뀌지 않는다."""
    before = _track_courses(legacy_course_api, track_id, educator_headers)

    response = legacy_course_api.add_track_course(
        track_id,
        None,
        educator_headers,
        confirmed=True,
    )
    assert_error_response(response, logic_error(400))

    after = _track_courses(legacy_course_api, track_id, educator_headers)
    assert after == before


@pytest.mark.mutating
@pytest.mark.educator
@pytest.mark.boundary
def test_tc097_track_course_move_rejects_invalid_order(
    allow_course_mutations: None,
    cleanup_registry: CleanupRegistry,
    educator_headers: dict,
    legacy_course_api: LegacyCourseApi,
    track_id: int,
) -> None:
    """TC97: 범위를 벗어난 순서 번호는 거부되고 목록은 유지된다."""
    before = _track_courses(legacy_course_api, track_id, educator_headers)
    before_ids = [course.get("course_id", course.get("id")) for course in before]

    def restore_if_changed() -> None:
        current = _track_courses(legacy_course_api, track_id, educator_headers)
        current_ids = [course.get("course_id", course.get("id")) for course in current]
        if current_ids == before_ids:
            return
        assert sorted(current_ids) == sorted(before_ids)
        for target_index, course_id in enumerate(before_ids):
            current_index = current_ids.index(course_id)
            if current_index == target_index:
                continue
            restore_response = legacy_course_api.move_track_course(
                track_id,
                current_index,
                target_index,
                educator_headers,
                confirmed=True,
            )
            assert_api_success(restore_response, expected_api_status_code=200)
            current_ids.insert(target_index, current_ids.pop(current_index))

    cleanup_registry.add(
        key=f"track:{track_id}:invalid-move",
        description="TC97 비정상 순서 변경 복구",
        callback=restore_if_changed,
    )

    response = legacy_course_api.move_track_course(
        track_id,
        2_147_483_647,
        2_147_483_646,
        educator_headers,
        confirmed=True,
    )
    assert_error_response(
        response,
        logic_error(409, error_code="invalid_order_no"),
    )

    after = _track_courses(legacy_course_api, track_id, educator_headers)
    assert after == before


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_tc102_learner_cannot_add_track_course(
    allow_course_mutations: None,
    boundary_course_id: int,
    cleanup_registry: CleanupRegistry,
    educator_headers: dict,
    learner_headers: dict,
    legacy_course_api: LegacyCourseApi,
    track_id: int,
) -> None:
    """TC102: 수강생의 관리자 전용 과목 추가 요청은 거부된다."""
    before = _track_courses(legacy_course_api, track_id, learner_headers)
    before_ids = [course.get("course_id", course.get("id")) for course in before]

    def remove_if_unexpectedly_added() -> None:
        current = _track_courses(legacy_course_api, track_id, educator_headers)
        current_ids = [course.get("course_id", course.get("id")) for course in current]
        if boundary_course_id in before_ids or boundary_course_id not in current_ids:
            return
        cleanup_response = legacy_course_api.remove_track_course(
            track_id,
            boundary_course_id,
            educator_headers,
            confirmed=True,
        )
        assert_api_success(cleanup_response, expected_api_status_code=200)

    cleanup_registry.add(
        key=f"track:{track_id}:course:{boundary_course_id}:permission-boundary",
        description="TC102 권한 오류 시 잘못 추가된 과목 제거",
        callback=remove_if_unexpectedly_added,
    )

    response = legacy_course_api.add_track_course(
        track_id,
        boundary_course_id,
        learner_headers,
        confirmed=True,
    )
    assert_error_response(
        response,
        logic_error(409, error_code="insufficient_permission"),
    )

    after = _track_courses(legacy_course_api, track_id, learner_headers)
    assert after == before
