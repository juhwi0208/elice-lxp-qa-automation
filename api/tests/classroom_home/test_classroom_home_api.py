"""클래스 홈 위젯을 구성하는 조회 API 검증(TC 54~63)."""

from datetime import UTC, datetime

import pytest

from part1_api_automation.tests.board.helpers import get_article
from part1_api_automation.utils import api_client
from part1_api_automation.utils.response import (
    assert_conflict,
    assert_forbidden,
    assert_http_status,
    assert_unprocessable_entity,
)


def _get_classroom_courses(learner_course_api, classroom_id: str) -> list[dict]:
    """과목 위젯 원본 API를 호출하고 공통 응답 계약을 검증한다."""
    response = learner_course_api.list_classroom_courses(classroom_id, count=100)
    assert_http_status(response, 200)
    courses = response.json()
    assert isinstance(courses, list), "클래스 과목 목록 응답은 배열이어야 합니다."
    return courses


def _get_classroom_schedules(
    classroom_api_base_url: str,
    classroom_id: str,
    learner_headers: dict,
    schedule_window: dict[str, str],
) -> list[dict]:
    """일정 위젯 원본 API를 호출하고 공통 응답 계약을 검증한다."""
    response = api_client.get(
        f"{classroom_api_base_url}/schedule",
        headers=learner_headers,
        params={**schedule_window, "classroom_id": classroom_id, "count": 50},
    )
    assert_http_status(response, 200)
    schedules = response.json()
    assert isinstance(schedules, list), "클래스 일정 목록 응답은 배열이어야 합니다."
    return schedules


def _course_identifier(course: dict) -> int:
    """과목 목록 응답에서 양의 정수 과목 ID를 반환한다."""
    course_id = course.get("course_id", course.get("id"))
    assert isinstance(course_id, int) and course_id > 0, (
        f"유효하지 않은 과목 ID입니다: {course_id!r}"
    )
    return course_id


def _parse_api_datetime(value: object, field_name: str) -> datetime:
    """API의 ISO 8601 날짜·시간 문자열을 비교 가능한 datetime으로 변환한다."""
    assert isinstance(value, str) and value.strip(), (
        f"{field_name}은 비어 있지 않은 ISO 8601 문자열이어야 합니다."
    )
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AssertionError(
            f"{field_name}이 ISO 8601 형식이 아닙니다: {value!r}"
        ) from exc
    # Calendar API는 일부 응답에서 UTC 오프셋을 생략하므로 UTC로 해석한다.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.classroom_home
def test_tc054_classroom_home_course_widget_matches_api(
    learner_course_api, classroom_id
):
    """TC054: 과목 위젯 원본 API가 표시 필드를 포함한 과목 목록을 반환한다."""
    courses = _get_classroom_courses(learner_course_api, classroom_id)
    assert courses, "과목 위젯 검증에 필요한 등록 과목이 없습니다."

    for index, course in enumerate(courses):
        assert isinstance(course, dict), f"과목[{index}]는 객체여야 합니다."
        missing_fields = {"course_id", "title"} - course.keys()
        assert not missing_fields, (
            f"과목[{index}] 표시 필드가 누락됐습니다: {sorted(missing_fields)}"
        )
        _course_identifier(course)
        assert isinstance(course["title"], str) and course["title"].strip(), (
            f"과목[{index}].title은 비어 있지 않은 문자열이어야 합니다."
        )


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.classroom_home
def test_tc055_classroom_home_course_ids_are_unique(learner_course_api, classroom_id):
    """TC055: 클래스 홈 과목 위젯에 같은 과목이 중복 노출되지 않는다."""
    courses = _get_classroom_courses(learner_course_api, classroom_id)
    ids = [_course_identifier(item) for item in courses]
    assert len(ids) == len(set(ids)), "클래스 홈 과목 위젯에 중복 과목이 반환되었습니다."


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.classroom_home
def test_tc056_classroom_home_schedule_widget_has_display_fields(
    classroom_api_base_url, classroom_id, learner_headers, schedule_window
):
    """TC056: 일정 위젯 원본 API가 화면 표시에 필요한 필드를 반환한다."""
    schedules = _get_classroom_schedules(
        classroom_api_base_url,
        classroom_id,
        learner_headers,
        schedule_window,
    )
    assert schedules, "일정 위젯 검증에 필요한 일정이 없습니다."

    for index, item in enumerate(schedules):
        assert isinstance(item, dict), f"일정[{index}]는 객체여야 합니다."
        missing_fields = {"id", "summary", "dt_start", "dt_end"} - item.keys()
        assert not missing_fields, (
            f"일정[{index}] 표시 필드가 누락됐습니다: {sorted(missing_fields)}"
        )
        schedule_id = item["id"]
        assert (
            isinstance(schedule_id, int)
            and not isinstance(schedule_id, bool)
            and schedule_id > 0
        ) or (isinstance(schedule_id, str) and bool(schedule_id.strip())), (
            f"일정[{index}].id는 유효한 정수 또는 문자열 식별자여야 합니다."
        )
        assert isinstance(item["summary"], str) and item["summary"].strip(), (
            f"일정[{index}].summary는 비어 있지 않은 문자열이어야 합니다."
        )
        start = _parse_api_datetime(item["dt_start"], f"일정[{index}].dt_start")
        end = _parse_api_datetime(item["dt_end"], f"일정[{index}].dt_end")
        assert start <= end, f"일정[{index}]의 종료 시간이 시작 시간보다 빠릅니다."


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.classroom_home
def test_tc057_classroom_home_schedule_is_in_requested_window(
    classroom_api_base_url, classroom_id, learner_headers, schedule_window
):
    """TC057: 일정 위젯 API가 요청한 시작일 범위의 일정만 반환한다."""
    schedules = _get_classroom_schedules(
        classroom_api_base_url,
        classroom_id,
        learner_headers,
        schedule_window,
    )
    range_start = _parse_api_datetime(schedule_window["dt_start_ge"], "dt_start_ge")
    range_end = _parse_api_datetime(schedule_window["dt_start_le"], "dt_start_le")

    for index, item in enumerate(schedules):
        actual_start = _parse_api_datetime(
            item.get("dt_start"),
            f"일정[{index}].dt_start",
        )
        assert range_start <= actual_start <= range_end, (
            f"일정[{index}]의 시작 시간이 요청 범위를 벗어났습니다: "
            f"{schedule_window['dt_start_ge']} <= {item.get('dt_start')} "
            f"<= {schedule_window['dt_start_le']}"
        )


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.classroom_home
def test_tc058_classroom_home_article_detail_matches_widget(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_reference,
):
    """TC058: 게시글 위젯 목록의 게시글과 상세 조회 데이터가 일치한다."""
    article_id = board_article_reference["id"]
    article = get_article(api_base_url, org_name_short, learner_headers, article_id)
    assert article.get("id") == article_id
    assert isinstance(article.get("title"), str) and article["title"].strip()

    summary = board_article_reference["summary"]
    if summary is not None:
        assert article.get("title") == summary.get("title"), (
            "게시글 목록과 상세 조회의 제목이 다릅니다."
        )
        if "is_secret" in summary:
            assert article.get("is_secret") == summary.get("is_secret"), (
                "게시글 목록과 상세 조회의 공개 여부가 다릅니다."
            )


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.classroom_home
def test_tc059_classroom_home_widget_requests_use_same_class_context(
    learner_course_api,
    classroom_api_base_url,
    classroom_id,
    course_id,
    learner_headers,
    schedule_window,
):
    """TC059: 과목·일정 위젯 데이터가 동일한 QA 클래스 범위에 속한다."""
    courses = _get_classroom_courses(learner_course_api, classroom_id)
    course_ids = {_course_identifier(item) for item in courses}
    assert course_id in course_ids, (
        f"QA 클래스의 기준 과목({course_id})이 과목 위젯 응답에 없습니다."
    )

    schedules = _get_classroom_schedules(
        classroom_api_base_url,
        classroom_id,
        learner_headers,
        schedule_window,
    )
    for index, item in enumerate(schedules):
        returned_classroom_id = item.get("classroom_id")
        if returned_classroom_id is not None:
            assert str(returned_classroom_id) == str(classroom_id), (
                f"일정[{index}]가 요청한 클래스와 다른 클래스에 속합니다."
            )
        returned_course_id = item.get("course_id")
        if returned_course_id is not None:
            assert returned_course_id in course_ids, (
                f"일정[{index}]가 클래스 과목 목록에 없는 과목을 참조합니다."
            )


@pytest.mark.read_only
@pytest.mark.learner
@pytest.mark.classroom_home
def test_tc060_course_widget_is_limited_to_enrolled_classroom(
    learner_course_api,
    classroom_id,
    course_id,
):
    """TC060: 과목 위젯에 QA 클래스에 등록된 기준 과목이 포함된다."""
    courses = _get_classroom_courses(learner_course_api, classroom_id)
    course_ids = {_course_identifier(item) for item in courses}
    assert course_id in course_ids, (
        f"QA 클래스에 등록된 기준 과목({course_id})이 반환되지 않았습니다."
    )

    for index, item in enumerate(courses):
        returned_classroom_id = item.get("classroom_id")
        if returned_classroom_id is not None:
            assert str(returned_classroom_id) == str(classroom_id), (
                f"과목[{index}]가 요청한 클래스와 다른 클래스에 속합니다."
            )


@pytest.mark.read_only
@pytest.mark.boundary
@pytest.mark.classroom_home
def test_tc061_classroom_home_apis_require_auth(
    classroom_api_base_url,
    classroom_id,
    org_name_short,
    schedule_window,
):
    """TC061: 과목·일정 위젯 API는 인증되지 않은 요청을 거부한다."""
    unauthenticated_headers = {"x-elice-org-name-short": org_name_short}
    course_response = api_client.get(
        f"{classroom_api_base_url}/classroom/{classroom_id}/course",
        headers=unauthenticated_headers,
        params={"count": 1, "skip": 0},
    )
    schedule_response = api_client.get(
        f"{classroom_api_base_url}/schedule",
        headers=unauthenticated_headers,
        params={**schedule_window, "classroom_id": classroom_id, "count": 1},
    )
    assert_forbidden(course_response)
    assert_forbidden(schedule_response)


@pytest.mark.read_only
@pytest.mark.boundary
@pytest.mark.classroom_home
def test_tc062_classroom_home_rejects_unknown_classroom(
    classroom_api_base_url,
    learner_headers,
    schedule_window,
):
    """TC062: 접근할 수 없는 정상 형식의 클래스 ID는 충돌 오류로 거부한다."""
    response = api_client.get(
        f"{classroom_api_base_url}/schedule",
        headers=learner_headers,
        params={
            **schedule_window,
            "classroom_id": "00000000-0000-0000-0000-000000000000",
            "count": 1,
        },
    )
    assert_conflict(response)


@pytest.mark.read_only
@pytest.mark.boundary
@pytest.mark.classroom_home
def test_tc063_classroom_home_rejects_missing_required_identifier(
    classroom_api_base_url,
    learner_headers,
    schedule_window,
):
    """TC063: 일정 위젯 API는 필수 클래스 ID가 없는 요청을 거부한다."""
    response = api_client.get(
        f"{classroom_api_base_url}/schedule",
        headers=learner_headers,
        params={**schedule_window, "count": 1},
    )
    assert_unprocessable_entity(response)
