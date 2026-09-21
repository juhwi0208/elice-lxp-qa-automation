"""test_learner_flow.py

수업 일정 학습자 정상 조회 테스트.
상태를 바꾸지 않는 GET /schedule 한 건만 실행한다.
"""

from datetime import UTC, datetime, timedelta

import pytest

from part1_api_automation.utils import api_client
from part1_api_automation.utils.response import assert_http_status


@pytest.mark.read_only
@pytest.mark.learner
def test_learner_gets_schedule_list(
    api_base_url, classroom_id, learner_headers, qa_schedule
):
    """[CS-001] 학습자가 QA 전용 클래스의 기간 일정 목록을 조회할 수 있는지 검증한다."""
    # 기간을 과거 30일 ~ 미래 30일로 넉넉하게 잡아 데이터 부족을 방지한다.
    now = datetime.now(UTC)
    start_at = now - timedelta(days=30)
    end_at = now + timedelta(days=30)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "count": 40,
        },
    )

    # 정상 HTTP 응답과 명세상 배열 응답을 확인한다.
    assert_http_status(response, 200)
    schedules = response.json()
    assert isinstance(schedules, list), "일정 목록 응답은 JSON 배열이어야 합니다."

    # 실제 일정 데이터가 하나라도 있어야 필드 검증이 가능하므로 빈 배열은 실패 처리한다.
    assert len(schedules) > 0, (
        "조회된 일정이 하나도 없어서 응답 필드를 검증할 수 없습니다."
    )

    required_fields = {"id", "summary", "dt_start", "dt_end"}
    for index, schedule in enumerate(schedules):
        missing_fields = required_fields - schedule.keys()
        assert not missing_fields, (
            f"일정[{index}]에 필수 필드가 없습니다: {sorted(missing_fields)}"
        )


@pytest.mark.read_only
@pytest.mark.learner
def test_learner_gets_schedule_by_date(
    api_base_url,
    classroom_id,
    learner_headers,
    qa_schedule,
):
    """[CS-002] 학습자가 특정 날짜의 수업 일정을 조회할 수 있는지 검증한다."""
    target_date = datetime.now(UTC).date().isoformat()

    response = api_client.get(
        url=f"{api_base_url}/schedule/by_date",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "date": target_date,
        },
    )

    assert_http_status(response, 200)

    schedules_by_date = response.json()
    assert isinstance(schedules_by_date, list), (
        "날짜별 일정 조회 응답은 JSON 배열이어야 합니다."
    )

    # 실제 일정 데이터가 하나라도 있어야 필드 검증이 가능하므로 빈 배열은 실패 처리한다.
    assert len(schedules_by_date) > 0, (
        "날짜별 일정이 하나도 없어서 응답 필드를 검증할 수 없습니다."
    )

    for index, item in enumerate(schedules_by_date):
        required_fields = {"date", "relative_date", "schedules"}
        missing_fields = required_fields - item.keys()
        assert not missing_fields, (
            f"날짜별 응답[{index}]에 필수 필드가 없습니다: {sorted(missing_fields)}"
        )
        assert isinstance(item["schedules"], list), (
            f"날짜별 응답[{index}]의 schedules는 배열이어야 합니다."
        )


@pytest.mark.read_only
@pytest.mark.learner
def test_learner_gets_schedule_count(
    api_base_url,
    classroom_id,
    learner_headers,
    qa_schedule,
):
    """[CS-003] 학습자가 기간 내 수업 일정 개수를 조회할 수 있는지 검증한다."""
    now = datetime.now(UTC)
    start_at = now - timedelta(days=30)
    end_at = now + timedelta(days=30)

    response = api_client.get(
        url=f"{api_base_url}/schedule/count",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
        },
    )

    assert_http_status(response, 200)

    result = response.json()
    assert isinstance(result, dict), "일정 개수 조회 응답은 JSON 객체여야 합니다."

    count = result.get("count")
    assert type(count) is int, "count는 정수여야 합니다."
    assert count >= 0, "count는 0 이상이어야 합니다."


@pytest.mark.read_only
@pytest.mark.learner
def test_learner_gets_schedule_summary(
    api_base_url,
    classroom_id,
    learner_headers,
    qa_schedule,
):
    """[CS-004] 학습자가 기간별 일정 요약 정보를 조회할 수 있는지 검증한다."""
    today = datetime.now(UTC).date()
    start_date = (today - timedelta(days=30)).isoformat()
    end_date = (today + timedelta(days=30)).isoformat()

    response = api_client.get(
        url=f"{api_base_url}/schedule/summary",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "date_start": start_date,
            "date_end": end_date,
        },
    )

    assert_http_status(response, 200)

    summary = response.json()
    assert isinstance(summary, dict), "일정 요약 조회 응답은 JSON 객체여야 합니다."

    days = summary.get("days")
    assert isinstance(days, list), "days는 배열이어야 합니다."
    assert len(days) > 0, "요약 데이터(days)가 비어 있어 필드 검증을 할 수 없습니다."

    for index, day in enumerate(days):
        required_fields = {"date", "schedule_exists"}
        missing_fields = required_fields - day.keys()
        assert not missing_fields, (
            f"days[{index}]에 필수 필드가 없습니다: {sorted(missing_fields)}"
        )
        assert day["date"] is None or isinstance(day["date"], str), (
            f"days[{index}].date는 문자열 또는 null이어야 합니다."
        )
        assert day["schedule_exists"] is None or isinstance(
            day["schedule_exists"], bool
        ), f"days[{index}].schedule_exists는 true, false 또는 null이어야 합니다."
