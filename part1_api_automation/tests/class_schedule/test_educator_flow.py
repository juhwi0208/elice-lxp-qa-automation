import warnings
from datetime import UTC, datetime, timedelta
import pytest
import uuid

from part1_api_automation.utils.api_client import AbortTestError
from part1_api_automation.utils.config import is_mutating_test_allowed
from part1_api_automation.utils import api_client
from part1_api_automation.utils.security import mask_sensitive_data
from part1_api_automation.utils.response import assert_http_status


def _fmt(value: datetime) -> str:
    """datetime을 API 요청 형식 문자열로 변환한다."""
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture
def cleanup_schedules(api_base_url, classroom_id, educator_headers):
    """
    테스트 중 생성된 일정 ID 리스트를 받아, 테스트 종료 시 강제로 삭제(정리)한다.
    테스트 본문이 중간에 실패하더라도 yield 이후의 삭제 코드가 보장된다.
    """
    created_ids = []
    yield created_ids

    for schedule_id in created_ids:
        try:
            api_client.delete(
                url=f"{api_base_url}/schedule/{schedule_id}",
                headers=educator_headers,
                json={"classroom_id": classroom_id},
                confirmed=True,
            )
        except Exception as e:
            warnings.warn(
                f"[cleanup_schedules] schedule_id={schedule_id} 정리 중 오류 발생: {e}",
                stacklevel=2,
            )


# ───────────────────────────────────────────────
# 실제 API 호출 테스트 — /schedule 정상 조회 통과 후 구현
# ───────────────────────────────────────────────


@pytest.mark.read_only
@pytest.mark.educator
def test_educator_gets_schedule_list(
    api_base_url, classroom_id, educator_headers, qa_schedule
):
    """교육자가 담당 클래스의 수업 일정 목록을 GET /schedule로 조회할 수 있는지 검증한다."""
    start_at = qa_schedule["start_at"] - timedelta(days=30)
    end_at = qa_schedule["start_at"] + timedelta(days=30)

    url = f"{api_base_url}/schedule"
    params = {
        "classroom_id": classroom_id,
        "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "count": 10,
    }

    response = api_client.get(url, headers=educator_headers, params=params)

    # 1. 정상 HTTP 응답
    assert_http_status(response, 200)

    # 2. 명세상 성공 응답은 배열
    schedules = response.json()
    assert isinstance(schedules, list), "수업 일정 목록 응답은 배열이어야 합니다."

    # 3. 일정이 있으면 각 항목의 필수 필드 확인
    required_fields = {"id", "summary", "dt_start", "dt_end"}
    for index, schedule in enumerate(schedules):
        missing = required_fields - schedule.keys()
        assert not missing, f"일정[{index}]에 필수 필드가 없습니다: {missing}"


@pytest.mark.mutating
@pytest.mark.educator
def test_educator_can_create_update_and_delete_one_qa_schedule(
    api_base_url,
    classroom_id,
    educator_headers,
    cleanup_schedules,
):
    """교육자가 QA 임시 일정을 생성·수정·삭제하고 삭제 후 미조회를 확인한다."""
    if not is_mutating_test_allowed():
        pytest.skip(
            "상태 변경 테스트는 개인 .env에서 명시적으로 허용한 경우에만 실행합니다."
        )

    start_at = (datetime.now(UTC) + timedelta(days=30)).replace(
        hour=2, minute=0, second=0, microsecond=0
    )
    end_at = start_at + timedelta(hours=1)
    initial_summary = f"[QA-AUTO] schedule-crud-{uuid.uuid4().hex[:8]}"
    initial_description = "QA 자동화 생성 전 설명"
    updated_description = "QA 자동화 수정 후 설명"
    schedule_id = None

    # 1. 교육자 권한으로 임시 일정 하나를 생성한다. (CREATE)
    create_response = api_client.post(
        url=f"{api_base_url}/schedule",
        headers=educator_headers,
        json={
            "classroom_id": classroom_id,
            "summary": initial_summary,
            "description": initial_description,
            "dt_start": _fmt(start_at),
            "dt_end": _fmt(end_at),
        },
        confirmed=True,
    )
    assert_http_status(create_response, 200)

    # 생성 후 ID를 찾아서 cleanup_schedules에 등록 (실패해도 자동 삭제 보장)
    created_schedules_response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=educator_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": _fmt(start_at - timedelta(days=1)),
            "dt_start_le": _fmt(end_at + timedelta(days=1)),
            "count": 40,
        },
    )
    assert created_schedules_response.status_code == 200
    created_schedules = created_schedules_response.json()
    created_schedule = next(
        (i for i in created_schedules if i.get("summary") == initial_summary), None
    )
    assert created_schedule is not None, (
        "생성한 [QA-AUTO] 일정이 목록에서 조회되지 않습니다."
    )

    schedule_id = created_schedule["id"]
    cleanup_schedules.append(schedule_id)

    # 2. 생성한 일정의 설명만 수정한다. (PATCH)
    update_response = api_client.patch(
        url=f"{api_base_url}/schedule/{schedule_id}",
        headers=educator_headers,
        json={
            "classroom_id": classroom_id,
            "description": updated_description,
        },
        confirmed=True,
    )
    assert update_response.status_code == 200, (
        f"교육자 일정 수정 실패: status={update_response.status_code}"
    )

    # 3. 수정 결과를 조회한다. 제목·시작·종료 시간은 그대로여야 한다. (GET)
    detail_response = api_client.get(
        url=f"{api_base_url}/schedule/{schedule_id}",
        headers=educator_headers,
        params={"classroom_id": classroom_id},
    )
    assert detail_response.status_code == 200, (
        f"수정한 일정 상세 조회 실패: status={detail_response.status_code}"
    )
    detail = detail_response.json()
    assert detail.get("description") == updated_description, (
        "설명이 수정되지 않았습니다."
    )
    assert detail.get("summary") == initial_summary, (
        "의도치 않게 제목이 변경되었습니다."
    )

    # 4. 일정을 삭제한다. (DELETE)
    delete_response = api_client.delete(
        url=f"{api_base_url}/schedule/{schedule_id}",
        headers=educator_headers,
        json={"classroom_id": classroom_id},
        confirmed=True,
    )
    assert delete_response.status_code == 200, (
        f"교육자 일정 삭제 실패: status={delete_response.status_code}"
    )

    # 정상적으로 삭제되었으므로 cleanup 대상에서 제외
    cleanup_schedules.remove(schedule_id)

    # 5. 삭제 후 목록에서 사라졌는지 확인한다. (GET 목록)
    remaining_response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=educator_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": _fmt(start_at - timedelta(days=1)),
            "dt_start_le": _fmt(end_at + timedelta(days=1)),
            "count": 40,
        },
    )
    assert remaining_response.status_code == 200
    remaining_schedules = remaining_response.json()
    assert not any(item.get("id") == schedule_id for item in remaining_schedules), (
        "삭제한 [QA-AUTO] 일정이 목록에 남아 있습니다."
    )
