"""TC86~92 학습과목 변경 API와 테스트 데이터 원복 검증."""

from __future__ import annotations

import json
import os

import pytest

from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import assert_api_success
from test_support.cleanup import CleanupRegistry


_COURSE_EDIT_REQUIRED_FIELDS = (
    "is_recommended",
    "is_chat_room_disabled",
    "is_post_student_info_visible",
    "is_post_student_email_enabled",
    "is_post_tutor_email_enabled",
    "is_enroll_noti_enabled",
    "enroll_type",
    "price",
    "completion_info",
    "title",
    "course_type",
    "code",
    "short_description",
    "target_audience",
    "objective",
    "faq",
    "class_times",
    "class_type",
    "period",
    "info_summary_visibility_dict",
    "leaderboard_info",
)

_LECTURE_EDIT_REQUIRED_FIELDS = (
    "course_id",
    "lecture_type",
    "title",
    "is_opened",
    "is_preview",
    "test_begin_datetime",
    "test_description",
    "is_test_accessible_after_completion",
    "is_test_accessible_after_prepare",
    "is_test_reset_enabled_by_student",
    "is_test_score_opened",
    "is_test_lecture_page_score_opened",
)


def _positive_env_or_skip(name: str) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        pytest.skip(f"학습과목 변경 API 환경변수 미설정: {name}")
    try:
        value = int(raw)
    except ValueError:
        pytest.fail(f"{name}은 양의 정수여야 합니다.")
    if value <= 0:
        pytest.fail(f"{name}은 양의 정수여야 합니다.")
    return value


def _json_env_or_skip(name: str) -> dict:
    raw = os.getenv(name, "").strip()
    if not raw:
        pytest.skip(f"학습과목 변경 API 환경변수 미설정: {name}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(f"{name}은 JSON 객체여야 합니다: {exc}")
    if not isinstance(value, dict) or not value:
        pytest.fail(f"{name}은 비어 있지 않은 JSON 객체여야 합니다.")
    return value


def _snapshot_restore_fields(
    before: dict,
    patch: dict,
    env_name: str,
) -> dict:
    """변경 대상 필드의 원래 값을 안전한 자동 원복 payload로 만든다."""
    missing_keys = [key for key in patch if key not in before]
    assert not missing_keys, (
        f"{env_name}의 필드가 조회 응답에 없습니다: {missing_keys}"
    )

    null_keys = [key for key in patch if before[key] is None]
    assert not null_keys, (
        f"{env_name}에서 원래 값이 null인 필드는 자동 원복을 보장할 수 없습니다: "
        f"{null_keys}"
    )
    return {key: before[key] for key in patch}


def _required_edit_fields(
    before: dict,
    required_fields: tuple[str, ...],
    object_name: str,
) -> dict:
    """전체 수정 API가 요구하는 기존 필드를 조회 결과에서 복원한다."""
    missing_keys = [key for key in required_fields if key not in before]
    assert not missing_keys, (
        f"{object_name} 조회 응답에 수정 API 필수 필드가 없습니다: {missing_keys}"
    )
    return {key: before[key] for key in required_fields}


def _track_courses(api: LegacyCourseApi, track_id: int, headers: dict) -> list[dict]:
    body = assert_api_success(
        api.get_track(track_id, headers),
        expected_api_status_code=200,
    )
    track = body.get("track")
    assert isinstance(track, dict)
    courses = track.get("courses")
    assert isinstance(courses, list)
    return courses


def _course_ids(courses: list[dict]) -> list[int]:
    ids = [course.get("course_id", course.get("id")) for course in courses]
    assert all(isinstance(course_id, int) for course_id in ids)
    return ids


def _success_object(
    response,
    object_key: str,
) -> dict:
    body = assert_api_success(response, expected_api_status_code=200)
    value = body.get(object_key)
    assert isinstance(value, dict)
    return value


@pytest.mark.mutating
@pytest.mark.educator
def test_tc086_educator_adds_track_course_and_cleanup_restores_it(
    allow_course_mutations: None,
    cleanup_registry: CleanupRegistry,
    educator_headers: dict,
    legacy_course_api: LegacyCourseApi,
    track_id: int,
) -> None:
    """TC86: 과목 추가 결과를 확인하고 종료 시 추가 과목을 삭제한다."""
    add_course_id = _positive_env_or_skip("LXP_TRACK_ADD_COURSE_ID")
    before_ids = _course_ids(_track_courses(legacy_course_api, track_id, educator_headers))
    if add_course_id in before_ids:
        pytest.skip("LXP_TRACK_ADD_COURSE_ID는 대상 트랙에 미등록된 과목이어야 합니다.")

    def restore() -> None:
        current_ids = _course_ids(
            _track_courses(legacy_course_api, track_id, educator_headers)
        )
        if add_course_id not in current_ids:
            return
        cleanup = legacy_course_api.remove_track_course(
            track_id,
            add_course_id,
            educator_headers,
            confirmed=True,
        )
        assert_api_success(cleanup, expected_api_status_code=200)
        assert _course_ids(
            _track_courses(legacy_course_api, track_id, educator_headers)
        ) == before_ids

    cleanup_registry.add(
        key=f"track:{track_id}:course:{add_course_id}",
        description="TC86 추가 과목 원복",
        callback=restore,
    )

    response = legacy_course_api.add_track_course(
        track_id,
        add_course_id,
        educator_headers,
        confirmed=True,
    )
    assert_api_success(response, expected_api_status_code=200)

    after_ids = _course_ids(_track_courses(legacy_course_api, track_id, educator_headers))
    assert after_ids.count(add_course_id) == 1
    assert all(course_id in after_ids for course_id in before_ids)


@pytest.mark.mutating
@pytest.mark.educator
def test_tc087_educator_moves_track_course_and_restores_order(
    allow_course_mutations: None,
    cleanup_registry: CleanupRegistry,
    educator_headers: dict,
    legacy_course_api: LegacyCourseApi,
    track_id: int,
) -> None:
    """TC87: 과목 순서를 한 칸 이동하고 테스트 종료 시 원래 순서로 복원한다."""
    before_ids = _course_ids(_track_courses(legacy_course_api, track_id, educator_headers))
    if len(before_ids) < 2:
        pytest.skip("TC87은 과목이 2개 이상인 QA 트랙이 필요합니다.")

    def restore() -> None:
        current_ids = _course_ids(
            _track_courses(legacy_course_api, track_id, educator_headers)
        )
        for target_index, course_id in enumerate(before_ids):
            current_index = current_ids.index(course_id)
            if current_index == target_index:
                continue
            cleanup = legacy_course_api.move_track_course(
                track_id,
                current_index,
                target_index,
                educator_headers,
                confirmed=True,
            )
            assert_api_success(cleanup, expected_api_status_code=200)
            current_ids.insert(target_index, current_ids.pop(current_index))
        assert _course_ids(
            _track_courses(legacy_course_api, track_id, educator_headers)
        ) == before_ids

    cleanup_registry.add(
        key=f"track:{track_id}:order",
        description="TC87 과목 순서 원복",
        callback=restore,
    )

    response = legacy_course_api.move_track_course(
        track_id,
        0,
        1,
        educator_headers,
        confirmed=True,
    )
    assert_api_success(response, expected_api_status_code=200)

    after_ids = _course_ids(_track_courses(legacy_course_api, track_id, educator_headers))
    assert after_ids[:2] == [before_ids[1], before_ids[0]]
    assert sorted(after_ids) == sorted(before_ids)


@pytest.mark.mutating
@pytest.mark.educator
def test_tc088_educator_edits_course_and_restores_fields(
    allow_course_mutations: None,
    cleanup_registry: CleanupRegistry,
    course_id: int,
    educator_headers: dict,
    legacy_course_api: LegacyCourseApi,
) -> None:
    """TC88: 과목 변경값을 재조회하고 실행 직전 값으로 자동 복구한다."""
    patch = _json_env_or_skip("LXP_COURSE_EDIT_PATCH_JSON")
    before = _success_object(
        legacy_course_api.get_course(course_id, educator_headers),
        "course",
    )
    restore_fields = _snapshot_restore_fields(
        before,
        patch,
        "LXP_COURSE_EDIT_PATCH_JSON",
    )
    base_fields = _required_edit_fields(
        before,
        _COURSE_EDIT_REQUIRED_FIELDS,
        "과목",
    )
    change_payload = {**base_fields, **patch}
    restore_payload = {**base_fields, **restore_fields}

    def restore() -> None:
        current = _success_object(
            legacy_course_api.get_course(course_id, educator_headers),
            "course",
        )
        if all(current.get(key) == before.get(key) for key in restore_fields):
            return
        cleanup = legacy_course_api.edit_course(
            course_id,
            restore_payload,
            educator_headers,
            confirmed=True,
        )
        assert_api_success(cleanup, expected_api_status_code=200)
        restored = _success_object(
            legacy_course_api.get_course(course_id, educator_headers),
            "course",
        )
        assert all(restored.get(key) == before.get(key) for key in restore_fields)

    cleanup_registry.add(
        key=f"course:{course_id}:fields",
        description="TC88 과목 정보 원복",
        callback=restore,
    )

    response = legacy_course_api.edit_course(
        course_id,
        change_payload,
        educator_headers,
        confirmed=True,
    )
    assert_api_success(response, expected_api_status_code=200)

    changed = _success_object(
        legacy_course_api.get_course(course_id, educator_headers),
        "course",
    )
    assert all(changed.get(key) == value for key, value in patch.items())


@pytest.mark.mutating
@pytest.mark.educator
def test_tc089_educator_edits_test_and_restores_fields(
    allow_course_mutations: None,
    cleanup_registry: CleanupRegistry,
    educator_headers: dict,
    lecture_id: int,
    legacy_course_api: LegacyCourseApi,
) -> None:
    """TC89: TEST 설정 변경을 재조회하고 실행 직전 값으로 자동 복구한다."""
    patch = _json_env_or_skip("LXP_LECTURE_EDIT_PATCH_JSON")
    before = _success_object(
        legacy_course_api.get_lecture(lecture_id, educator_headers),
        "lecture",
    )
    restore_fields = _snapshot_restore_fields(
        before,
        patch,
        "LXP_LECTURE_EDIT_PATCH_JSON",
    )
    base_fields = _required_edit_fields(
        before,
        _LECTURE_EDIT_REQUIRED_FIELDS,
        "수업",
    )
    change_payload = {**base_fields, **patch}
    restore_payload = {**base_fields, **restore_fields}

    def restore() -> None:
        current = _success_object(
            legacy_course_api.get_lecture(lecture_id, educator_headers),
            "lecture",
        )
        if all(current.get(key) == before.get(key) for key in restore_fields):
            return
        cleanup = legacy_course_api.edit_lecture(
            lecture_id,
            restore_payload,
            educator_headers,
            confirmed=True,
        )
        assert_api_success(cleanup, expected_api_status_code=200)
        restored = _success_object(
            legacy_course_api.get_lecture(lecture_id, educator_headers),
            "lecture",
        )
        assert all(restored.get(key) == before.get(key) for key in restore_fields)

    cleanup_registry.add(
        key=f"lecture:{lecture_id}:fields",
        description="TC89 TEST 설정 원복",
        callback=restore,
    )

    response = legacy_course_api.edit_lecture(
        lecture_id,
        change_payload,
        educator_headers,
        confirmed=True,
    )
    assert_api_success(response, expected_api_status_code=200)

    changed = _success_object(
        legacy_course_api.get_lecture(lecture_id, educator_headers),
        "lecture",
    )
    assert all(changed.get(key) == value for key, value in patch.items())


@pytest.mark.mutating
@pytest.mark.educator
def test_tc090_educator_changes_page_visibility_and_restores_it(
    allow_course_mutations: None,
    cleanup_registry: CleanupRegistry,
    educator_headers: dict,
    lecture_page_id: int,
    legacy_course_api: LegacyCourseApi,
) -> None:
    """TC90: 자료 공개·통계 상태를 변경하고 원래 두 값으로 복구한다."""
    before = _success_object(
        legacy_course_api.get_lecture_page(lecture_page_id, educator_headers),
        "lecture_page",
    )
    original_opened = before.get("is_opened")
    original_for_stats = before.get("is_for_stats")
    assert isinstance(original_opened, bool)
    assert isinstance(original_for_stats, bool)

    def restore() -> None:
        cleanup = legacy_course_api.edit_lecture_page_visibility(
            lecture_page_id,
            is_for_stats=original_for_stats,
            is_opened=original_opened,
            headers=educator_headers,
            confirmed=True,
        )
        assert_api_success(cleanup, expected_api_status_code=200)

    cleanup_registry.add(
        key=f"lecture-page:{lecture_page_id}:visibility",
        description="TC90 수업 자료 공개 상태 원복",
        callback=restore,
    )

    response = legacy_course_api.edit_lecture_page_visibility(
        lecture_page_id,
        is_for_stats=not original_for_stats,
        is_opened=not original_opened,
        headers=educator_headers,
        confirmed=True,
    )
    assert_api_success(response, expected_api_status_code=200)

    changed = _success_object(
        legacy_course_api.get_lecture_page(lecture_page_id, educator_headers),
        "lecture_page",
    )
    assert changed.get("is_opened") is not original_opened
    assert changed.get("is_for_stats") is not original_for_stats


@pytest.mark.mutating
@pytest.mark.learner
def test_tc091_learner_submits_quiz_response_and_cleanup_resets_it(
    allow_course_mutations: None,
    cleanup_registry: CleanupRegistry,
    educator_headers: dict,
    learner_headers: dict,
    learner_user_id: int,
    legacy_course_api: LegacyCourseApi,
    quiz_resource_id: int | None,
) -> None:
    """TC91: 학습자가 응답을 저장·검증하고 자신의 응답을 초기화한다."""
    material_quiz_id = _positive_env_or_skip("LXP_TC91_MATERIAL_QUIZ_ID")
    answer = os.getenv("LXP_QUIZ_ANSWER", "").strip()
    if not answer:
        pytest.skip("TC91은 LXP_QUIZ_ANSWER가 필요합니다.")
    if os.getenv("LXP_ALLOW_IRREVERSIBLE_TEST_RESET", "false").strip().lower() != "true":
        pytest.skip(
            "TC91 cleanup은 학습자 응답을 초기화하므로 "
            "LXP_ALLOW_IRREVERSIBLE_TEST_RESET=true가 필요합니다."
        )
    try:
        expected_answer = json.loads(answer)
    except json.JSONDecodeError as exc:
        pytest.fail(f"LXP_QUIZ_ANSWER는 JSON 값이어야 합니다: {exc}")

    existing_body = assert_api_success(
        legacy_course_api.list_material_quiz_responses(
            material_quiz_id,
            None,
            educator_headers,
            offset=0,
            count=20,
            contain_only_last=False,
            include_answer=False,
        ),
        expected_api_status_code=200,
    )
    existing_responses = existing_body.get("quiz_responses")
    assert isinstance(existing_responses, list)
    if existing_responses:
        pytest.skip(
            "TC91의 HeadTA cleanup은 해당 퀴즈 응답 전체에 영향을 줄 수 있습니다. "
            "기존 응답이 없는 TC91 전용 QA 퀴즈를 "
            "LXP_TC91_MATERIAL_QUIZ_ID로 지정하세요. "
            f"현재 응답 수: {len(existing_responses)}"
        )

    response = legacy_course_api.add_material_quiz_response(
        material_quiz_id,
        quiz_resource_id,
        answer,
        learner_headers,
        confirmed=True,
    )
    body = assert_api_success(response, expected_api_status_code=200)
    response_id = body.get("quiz_response_id")
    if response_id is None and isinstance(body.get("quiz_response"), dict):
        response_id = body["quiz_response"].get("id")
    assert isinstance(response_id, int) and response_id > 0

    def restore() -> None:
        current_body = assert_api_success(
            legacy_course_api.list_material_quiz_responses(
                material_quiz_id,
                None,
                educator_headers,
                offset=0,
                count=20,
                contain_only_last=False,
                include_answer=False,
            ),
            expected_api_status_code=200,
        )
        current_responses = current_body.get("quiz_responses")
        assert isinstance(current_responses, list)
        current_ids = {
            item.get("id") for item in current_responses if isinstance(item, dict)
        }
        assert current_ids <= {response_id}, (
            "TC91 실행 중 다른 사용자의 응답이 생성되어 전역 초기화를 중단합니다. "
            f"예상하지 못한 응답 ID: {sorted(current_ids - {response_id})}"
        )
        cleanup = legacy_course_api.reset_material_quiz_response(
            material_quiz_id,
            educator_headers,
            user_id=learner_user_id,
            confirmed=True,
        )
        assert_api_success(cleanup, expected_api_status_code=200)
        cleared_body = assert_api_success(
            legacy_course_api.list_material_quiz_responses(
                material_quiz_id,
                learner_user_id,
                educator_headers,
                offset=0,
                count=20,
                contain_only_last=False,
                include_answer=False,
            ),
            expected_api_status_code=200,
        )
        cleared_responses = cleared_body.get("quiz_responses")
        assert isinstance(cleared_responses, list)
        assert not any(
            isinstance(item, dict) and item.get("id") == response_id
            for item in cleared_responses
        ), "TC91에서 생성한 학습자 퀴즈 응답이 초기화되지 않았습니다."

    cleanup_registry.add(
        key=f"quiz-response:{response_id}",
        description="TC91 학습자 퀴즈 응답 초기화",
        callback=restore,
    )

    saved = _success_object(
        legacy_course_api.get_material_quiz_response(response_id, learner_headers),
        "quiz_response",
    )
    assert saved.get("material_quiz_id", material_quiz_id) == material_quiz_id
    assert saved.get("answer") == expected_answer


@pytest.mark.mutating
@pytest.mark.learner
def test_tc092_learner_resets_own_test_admission(
    allow_course_mutations: None,
    educator_headers: dict,
    learner_headers: dict,
    learner_user_id: int,
    lecture_id: int,
    legacy_course_api: LegacyCourseApi,
) -> None:
    """TC92: 폐기 가능한 QA 응시 이력만 명시적 승인 후 초기화한다."""
    if os.getenv("LXP_ALLOW_IRREVERSIBLE_TEST_RESET", "false").strip().lower() != "true":
        pytest.skip("TC92는 LXP_ALLOW_IRREVERSIBLE_TEST_RESET=true가 필요합니다.")

    before = assert_api_success(
        legacy_course_api.list_test_admissions(
            learner_user_id,
            lecture_id,
            educator_headers,
        ),
        expected_api_status_code=200,
    )
    before_items = before.get("test_admissions")
    assert isinstance(before_items, list) and before_items, (
        "TC92는 초기화할 QA TEST 응시 이력이 필요합니다."
    )
    before_lecture = _success_object(
        legacy_course_api.get_lecture(lecture_id, learner_headers),
        "lecture",
    )
    before_admission_status = before_lecture.get("test_admission_status")
    before_user_status = before_lecture.get("test_user_status")
    if before_admission_status == 0 and before_user_status == 0:
        pytest.skip("TC92 대상 시험이 이미 재응시 가능한 초기 상태입니다.")

    response = legacy_course_api.reset_test_by_self(
        lecture_id,
        learner_headers,
        confirmed=True,
    )
    assert_api_success(response, expected_api_status_code=200)

    after = assert_api_success(
        legacy_course_api.list_test_admissions(
            learner_user_id,
            lecture_id,
            educator_headers,
        ),
        expected_api_status_code=200,
    )
    after_items = after.get("test_admissions")
    assert isinstance(after_items, list)
    assert after_items != before_items
    after_lecture = _success_object(
        legacy_course_api.get_lecture(lecture_id, learner_headers),
        "lecture",
    )
    assert after_lecture.get("test_admission_status") == 0
    assert after_lecture.get("test_user_status") == 0
