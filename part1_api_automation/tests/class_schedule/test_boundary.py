from part1_api_automation.utils.config import is_mutating_test_allowed
from datetime import UTC, datetime, timedelta
import pytest
from part1_api_automation.utils import api_client
from part1_api_automation.utils.response import (
    assert_bad_request,
    assert_conflict,
    assert_forbidden,
    assert_http_status,
    assert_unauthorized,
    assert_unprocessable_entity,
)


@pytest.mark.read_only
@pytest.mark.boundary
def test_unauthenticated_request_is_rejected(api_base_url, org_name_short, classroom_id):
    """[CS-012] 인증 토큰 없이 GET /schedule 호출 시 인증 에러가 반환되는지 확인한다."""
    end_at = datetime.now(UTC)
    start_at = end_at - timedelta(days=30)

    url = f"{api_base_url}/schedule"
    params = {
        "classroom_id": classroom_id,
        "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "count": 5,
    }

    # 인증 헤더 없이 기관 헤더만 전달 (서버는 no_access_token 코드와 함께 403 Forbidden 반환)
    headers = {"x-elice-org-name-short": org_name_short}
    response = api_client.get(url, headers=headers, params=params)

    assert_forbidden(response)


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_rejects_invalid_token(api_base_url, org_name_short, classroom_id):
    """[CS-012-보조] 유효하지 않은 인증 토큰으로 GET /schedule 호출 시 거부되는지 확인한다."""
    end_at = datetime.now(UTC)
    start_at = end_at - timedelta(days=30)

    url = f"{api_base_url}/schedule"
    params = {
        "classroom_id": classroom_id,
        "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "count": 5,
    }

    # 위조/유효하지 않은 Bearer 토큰 전달
    headers = {
        "Authorization": "Bearer invalid_fake_token_12345",
        "x-elice-org-name-short": org_name_short,
    }
    response = api_client.get(url, headers=headers, params=params)

    assert response.status_code in (401, 403, 409), (
        f"유효하지 않은 토큰 요청인데 거부되지 않았습니다: {response.status_code}"
    )
    assert response.status_code != 500, "위조 토큰 요청 시 서버 500 오류가 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_invalid_classroom_id_returns_fail(api_base_url, learner_headers):
    """[CS-006-보조] 존재하지 않는 classroom_id로 GET /schedule 조회 시 실패 응답이 반환되는지 확인한다."""
    end_at = datetime.now(UTC)
    start_at = end_at - timedelta(days=30)

    url = f"{api_base_url}/schedule"
    params = {
        "classroom_id": "invalid-uuid-format-or-fake-id",
        "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "count": 5,
    }

    response = api_client.get(url, headers=learner_headers, params=params)

    assert_unprocessable_entity(response)


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_requires_classroom_id(
    api_base_url,
    learner_headers,
):
    """[CS-006] classroom_id 없이 일정 목록을 조회하면 검증 오류가 반환되는지 확인한다."""
    end_at = datetime.now(UTC)
    start_at = end_at - timedelta(days=30)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            # classroom_id는 의도적으로 넣지 않는다.
            "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "count": 10,
        },
    )

    # 필수값 누락은 400 또는 422로 처리될 수 있다.
    assert response.status_code == 422, (
        "classroom_id가 없는데 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_requires_start_datetime(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-007] dt_start_ge(시작일) 파라미터 누락 시 422 검증 오류가 반환되는지 확인한다."""
    end_at = datetime.now(UTC)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "count": 10,
        },
    )

    assert response.status_code == 422, (
        "dt_start_ge 파라미터가 누락되었는데 422 검증 오류가 발생하지 않았습니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_requires_end_datetime(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-008] dt_start_le(종료일) 파라미터 누락 시 422 검증 오류가 반환되는지 확인한다."""
    start_at = datetime.now(UTC) - timedelta(days=30)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "count": 10,
        },
    )

    assert response.status_code == 422, (
        "dt_start_le 파라미터가 누락되었는데 422 검증 오류가 발생하지 않았습니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_requires_count(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-009] count 파라미터 누락 시 422 검증 오류가 반환되는지 확인한다."""
    end_at = datetime.now(UTC)
    start_at = end_at - timedelta(days=30)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            # count 파라미터를 의도적으로 제외
        },
    )

    assert response.status_code == 422, (
        "count 파라미터가 누락되었는데 422 검증 오류가 발생하지 않았습니다: "
        f"{response.status_code}"
    )


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_missing_count_prevents_500_error(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-009-보조] count 파라미터 누락 시 서버 500 오류가 발생하지 않는지 확인한다."""
    end_at = datetime.now(UTC)
    start_at = end_at - timedelta(days=30)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            # count 파라미터를 의도적으로 제외
        },
    )

    assert response.status_code != 500, (
        f"count 누락 요청에 대해 서버 500 내부 오류가 발생했습니다: {response.status_code}"
    )
    assert response.status_code in (400, 422), (
        f"예상하지 못한 비정상 상태 코드입니다: {response.status_code}"
    )


def _has_permission_error(response) -> bool:
    """인증된 학습자의 권한 거부는 정확히 HTTP 403으로 판정한다."""
    return response.status_code == 403


@pytest.mark.mutating
@pytest.mark.boundary
@pytest.mark.skipif(
    not is_mutating_test_allowed(),
    reason="상태 변경 테스트는 개인 .env에서 명시적으로 허용한 경우에만 실행합니다.",
)
def test_learner_cannot_create_schedule(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-015] 학습자 토큰으로 일정 생성을 시도하면 권한 오류가 반환되는지 확인한다."""
    start_at = (datetime.now(UTC) + timedelta(days=30)).replace(
        hour=2, minute=0, second=0, microsecond=0
    )
    end_at = start_at + timedelta(hours=1)

    response = api_client.post(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        json={
            "classroom_id": classroom_id,
            "summary": "[QA-AUTO] learner-permission-check",
            "dt_start": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "dt_end": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        },
        confirmed=True,
    )

    assert_forbidden(response)


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_rejects_invalid_datetime_format(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-010] 잘못된 dt_start_ge 형식은 검증 오류로 처리되어야 한다."""
    end_at = datetime.now(UTC)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": "not-a-valid-datetime",
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "count": 10,
        },
    )

    assert response.status_code == 422, (
        "잘못된 날짜 형식인데 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_missing_schedule_detail_is_not_returned(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-011] 존재하지 않는 일정 상세 조회는 오류로 처리되어야 한다."""
    missing_schedule_id = "00000000-0000-0000-0000-000000000000"

    response = api_client.get(
        url=f"{api_base_url}/schedule/{missing_schedule_id}",
        headers=learner_headers,
        params={"classroom_id": classroom_id},
    )

    assert response.status_code == 409, (
        "존재하지 않는 일정 상세 조회에 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "존재하지 않는 리소스 조회로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_by_date_requires_date(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-019] date 없이 날짜별 일정 조회를 하면 검증 오류가 반환되어야 한다."""
    response = api_client.get(
        url=f"{api_base_url}/schedule/by_date",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            # date는 의도적으로 넣지 않는다.
        },
    )

    assert response.status_code == 422, (
        "date가 없는데 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_by_date_rejects_invalid_date_format(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-020] 잘못된 date 형식은 검증 오류로 처리되어야 한다."""
    response = api_client.get(
        url=f"{api_base_url}/schedule/by_date",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "date": "not-a-valid-date",
        },
    )

    assert response.status_code == 422, (
        "잘못된 date 형식인데 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_count_requires_start_datetime(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-021] count 조회에서 필수 시작일 누락은 검증 오류로 처리되어야 한다."""
    end_at = datetime.now(UTC)

    response = api_client.get(
        url=f"{api_base_url}/schedule/count",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            # dt_start_ge는 의도적으로 넣지 않는다.
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        },
    )

    assert response.status_code == 422, (
        "count 조회에 시작일이 없는데 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_summary_requires_date_start(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-023] summary 조회에서 date_start 누락은 검증 오류로 처리되어야 한다."""
    date_end = datetime.now(UTC).date().isoformat()

    response = api_client.get(
        url=f"{api_base_url}/schedule/summary",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            # date_start는 의도적으로 넣지 않는다.
            "date_end": date_end,
        },
    )

    assert response.status_code == 422, (
        "summary 조회에 date_start가 없는데 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_detail_requires_classroom_id(
    api_base_url,
    learner_headers,
):
    """[CS-025] 일정 상세 조회에서 classroom_id 누락은 검증 오류로 처리되어야 한다."""
    missing_schedule_id = "00000000-0000-0000-0000-000000000000"

    response = api_client.get(
        url=f"{api_base_url}/schedule/{missing_schedule_id}",
        headers=learner_headers,
        params={
            # classroom_id는 의도적으로 넣지 않는다.
        },
    )

    assert response.status_code == 422, (
        "상세 조회에 classroom_id가 없는데 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


def _assert_error_or_empty_list(response, scenario: str) -> None:
    """기간/개수 입력 경계는 캘린더 서비스 비즈니스 규칙에 따라 정확히 HTTP 409 Conflict로 판정한다."""
    try:
        assert_conflict(response)
    except AssertionError as exc:
        raise AssertionError(f"{scenario}: HTTP 409가 필요합니다. {exc}") from exc


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_handles_reversed_date_range(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-013] 시작일이 종료일보다 늦으면 4xx 또는 빈 목록으로 처리되어야 한다."""
    later = datetime.now(UTC)
    earlier = later - timedelta(days=7)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": later.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "dt_start_le": earlier.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "count": 10,
        },
    )

    _assert_error_or_empty_list(response, "역전된 일정 목록 기간")


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_count_allows_same_start_and_end(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-022] 시작·종료가 같은 시각이어도 count는 0 이상 정수로 반환되어야 한다."""
    point_at = datetime.now(UTC).replace(microsecond=0)
    point_text = point_at.isoformat(
        timespec="milliseconds").replace("+00:00", "Z")

    response = api_client.get(
        url=f"{api_base_url}/schedule/count",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": point_text,
            "dt_start_le": point_text,
        },
    )

    assert response.status_code == 200, (
        "시작·종료가 같은 시각인 count 조회가 실패했습니다: "
        f"{response.status_code}"
    )
    data = response.json()
    assert isinstance(data.get("count"), int) and data["count"] >= 0, (
        f"count는 0 이상 정수여야 합니다. 실제={data!r}"
    )


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_summary_handles_reversed_date_range(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-024] summary 역전 기간은 4xx 또는 빈 days로 처리되어야 한다."""
    later_date = datetime.now(UTC).date()
    earlier_date = later_date - timedelta(days=7)

    response = api_client.get(
        url=f"{api_base_url}/schedule/summary",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "date_start": later_date.isoformat(),
            "date_end": earlier_date.isoformat(),
        },
    )

    assert_conflict(response)


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_count_zero_returns_error_or_empty_list(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-026] count=0은 4xx 또는 빈 목록 정책으로 처리되어야 한다."""
    end_at = datetime.now(UTC)
    start_at = end_at - timedelta(days=30)

    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "dt_start_le": end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "count": 0,
        },
    )

    _assert_error_or_empty_list(response, "일정 목록 count=0")


def _recent_schedule_window() -> tuple[str, str]:
    """오늘 전후 30일(총 60일)의 UTC 조회 기간을 만든다."""
    now = datetime.now(UTC)
    start_at = now - timedelta(days=30)
    end_at = now + timedelta(days=30)
    return (
        start_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        end_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    )


def _get_one_schedule_or_skip(api_base_url, classroom_id, learner_headers) -> dict:
    """상세·일관성 조회에 쓸 기존 일정 하나를 안전하게 찾는다."""
    start_text, end_text = _recent_schedule_window()
    response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_text,
            "dt_start_le": end_text,
            "count": 40,
        },
    )
    assert response.status_code == 200, f"기준 일정 목록 조회 실패: {response.status_code}"
    schedules = response.json()
    assert isinstance(schedules, list), "일정 목록 응답은 배열이어야 합니다."
    if not schedules:
        pytest.skip("최근 30일에 상세·일관성 비교용 일정이 없어 안전하게 건너뜁니다.")
    return schedules[0]


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_detail_returns_existing_schedule(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-005] 일정 목록의 기존 일정은 상세 조회에서도 동일하게 반환되어야 한다."""
    schedule = _get_one_schedule_or_skip(
        api_base_url, classroom_id, learner_headers)
    schedule_id = schedule.get("id")
    assert schedule_id, "기준 일정에 id가 없습니다."

    response = api_client.get(
        url=f"{api_base_url}/schedule/{schedule_id}",
        headers=learner_headers,
        params={"classroom_id": classroom_id},
    )

    assert response.status_code == 200, f"기존 일정 상세 조회 실패: {response.status_code}"
    detail = response.json()
    assert isinstance(detail, dict), "일정 상세 응답은 객체여야 합니다."
    assert detail.get("id") == schedule_id, "목록에서 선택한 일정과 상세 응답의 id가 다릅니다."
    for field in ("summary", "dt_start", "dt_end"):
        assert field in detail, f"일정 상세 응답에 {field} 필드가 없습니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_ics_export_returns_content(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-014] 유효한 기간의 ICS 내보내기는 비어 있지 않은 성공 응답을 반환해야 한다."""
    start_text, end_text = _recent_schedule_window()

    response = api_client.get(
        url=f"{api_base_url}/schedule/ics",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_text,
            "dt_start_le": end_text,
            "count": 40,
        },
    )

    assert response.status_code == 200, f"ICS 내보내기 실패: {response.status_code}"
    assert response.content, "ICS 내보내기 성공 응답의 본문이 비어 있습니다."


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_list_count_matches_count_endpoint(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-017] 동일 기간에서 일정 목록 길이와 count 값은 일치해야 한다."""
    start_text, end_text = _recent_schedule_window()
    common_params = {
        "classroom_id": classroom_id,
        "dt_start_ge": start_text,
        "dt_start_le": end_text,
    }

    list_response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=learner_headers,
        params={**common_params, "count": 40},
    )
    count_response = api_client.get(
        url=f"{api_base_url}/schedule/count",
        headers=learner_headers,
        params=common_params,
    )

    assert list_response.status_code == 200, f"일정 목록 조회 실패: {list_response.status_code}"
    assert count_response.status_code == 200, f"일정 count 조회 실패: {count_response.status_code}"
    schedules = list_response.json()
    count_data = count_response.json()
    assert isinstance(schedules, list), "일정 목록 응답은 배열이어야 합니다."
    assert isinstance(count_data.get("count"),
                      int), "count 응답의 count는 정수여야 합니다."
    assert len(schedules) == count_data["count"], (
        f"목록 건수({len(schedules)})와 count({count_data['count']})가 다릅니다."
    )


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_summary_matches_by_date_for_a_scheduled_day(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-018] summary에서 일정 있음인 날짜는 by_date에서도 일정이 있어야 한다."""
    start_text, end_text = _recent_schedule_window()
    start_date = start_text[:10]
    end_date = end_text[:10]

    summary_response = api_client.get(
        url=f"{api_base_url}/schedule/summary",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "date_start": start_date,
            "date_end": end_date,
        },
    )
    assert summary_response.status_code == 200, (
        f"일정 summary 조회 실패: {summary_response.status_code}"
    )
    days = summary_response.json().get("days", [])
    assert isinstance(days, list), "summary 응답의 days는 배열이어야 합니다."

    scheduled_day = next(
        (day for day in days if day.get("schedule_exists") is True and day.get("date")),
        None,
    )
    if scheduled_day is None:
        pytest.skip("최근 30일 summary에 일정이 있는 날짜가 없어 안전하게 건너뜁니다.")

    by_date_response = api_client.get(
        url=f"{api_base_url}/schedule/by_date",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "date": scheduled_day["date"],
        },
    )
    assert by_date_response.status_code == 200, (
        f"날짜별 일정 조회 실패: {by_date_response.status_code}"
    )
    by_date_data = by_date_response.json()
    assert isinstance(by_date_data, list), "날짜별 일정 응답은 배열이어야 합니다."
    assert any(item.get("schedules") for item in by_date_data), (
        "summary에서 일정 있음인 날짜인데 by_date 결과에 일정이 없습니다."
    )


@pytest.mark.read_only
@pytest.mark.boundary
def test_schedule_ics_requires_count(
    api_base_url,
    classroom_id,
    learner_headers,
):
    """[CS-027] ICS 내보내기에서 count 누락은 4xx 검증 오류로 처리되어야 한다."""
    start_text, end_text = _recent_schedule_window()

    response = api_client.get(
        url=f"{api_base_url}/schedule/ics",
        headers=learner_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": start_text,
            "dt_start_le": end_text,
            # count는 의도적으로 넣지 않는다.
        },
    )

    assert response.status_code == 422, (
        "ICS count가 없는데 정상 응답이 왔거나 예상 밖 상태 코드입니다: "
        f"{response.status_code}"
    )
    assert response.status_code != 500, "입력값 오류로 서버 500이 발생하면 안 됩니다."


@pytest.mark.mutating
@pytest.mark.boundary
@pytest.mark.skipif(
    not is_mutating_test_allowed(),
    reason="상태 변경 테스트는 개인 .env에서 명시적으로 허용한 경우에만 실행합니다.",
)
def test_learner_cannot_update_or_delete_qa_schedule(
    api_base_url,
    classroom_id,
    educator_headers,
    learner_headers,
):
    """[CS-016] 학습자는 QA 임시 일정을 수정·삭제할 수 없고 원본은 보존되어야 한다."""
    # UTC 18:00 = KST 다음 날 03:00. 7~13일 뒤에서 비어 있는 한 시간만 선택한다.
    slot_start = None
    slot_end = None
    first_candidate = datetime.now(UTC) + timedelta(days=7)

    for day_offset in range(7):
        candidate_start = (first_candidate + timedelta(days=day_offset)).replace(
            hour=18, minute=0, second=0, microsecond=0
        )
        candidate_end = candidate_start + timedelta(hours=1)
        availability_response = api_client.get(
            url=f"{api_base_url}/schedule",
            headers=educator_headers,
            params={
                "classroom_id": classroom_id,
                "dt_start_ge": candidate_start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "dt_start_le": candidate_end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "count": 40,
            },
        )
        assert availability_response.status_code == 200, (
            f"QA 임시 일정 시간대 조회 실패: {availability_response.status_code}"
        )
        if availability_response.json() == []:
            slot_start = candidate_start
            slot_end = candidate_end
            break

    if slot_start is None or slot_end is None:
        pytest.skip("향후 7일 안에 QA 임시 일정을 만들 빈 시간대를 찾지 못했습니다.")

    original_summary = f"[QA-AUTO] learner-mutation-guard-{slot_start.strftime('%Y%m%d%H%M%S')}"
    original_description = "[QA-AUTO] temporary permission-boundary test"
    schedule_id = None

    try:
        print(f"\n[1/7] 교육자 - 임시 일정 생성 중...")
        print(f"      제목: {original_summary}")
        print(
            f"      시간: {slot_start.strftime('%Y-%m-%d %H:%M')} ~ {slot_end.strftime('%H:%M')} (UTC)")
        create_response = api_client.post(
            url=f"{api_base_url}/schedule",
            headers=educator_headers,
            json={
                "classroom_id": classroom_id,
                "summary": original_summary,
                "description": original_description,
                "dt_start": slot_start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "dt_end": slot_end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            },
            confirmed=True,
        )
        print(f"      → 생성 결과: HTTP {create_response.status_code}")
        assert_http_status(create_response, 200)

        print(f"[2/7] 교육자 - 생성된 일정 ID 확인 중...")
        find_response = api_client.get(
            url=f"{api_base_url}/schedule",
            headers=educator_headers,
            params={
                "classroom_id": classroom_id,
                "dt_start_ge": (slot_start - timedelta(hours=1)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "dt_start_le": (slot_end + timedelta(hours=1)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "count": 40,
            },
        )
        assert find_response.status_code == 200, (
            f"생성한 QA 임시 일정 목록 조회 실패: {find_response.status_code}"
        )
        matches = [item for item in find_response.json(
        ) if item.get("summary") == original_summary]
        assert len(matches) == 1, "생성한 QA 임시 일정을 정확히 하나 찾지 못했습니다."
        schedule_id = matches[0]["id"]
        print(f"      → schedule_id: {schedule_id}")

        print(f"[3/7] 학습자 - PATCH 시도 (거부 예상)...")
        patch_response = api_client.patch(
            url=f"{api_base_url}/schedule/{schedule_id}",
            headers=learner_headers,
            json={
                "classroom_id": classroom_id,
                "description": "[QA-AUTO] learner must not change this",
            },
            confirmed=True,
        )
        print(
            f"      → PATCH 응답: HTTP {patch_response.status_code} ({'BLOCKED' if _has_permission_error(patch_response) else 'NOT BLOCKED!'})")
        assert _has_permission_error(patch_response), (
            f"[보안 이슈] 학습자 PATCH가 차단되지 않았습니다: {patch_response.status_code}"
        )

        print(f"[4/7] 학습자 - DELETE 시도 (거부 예상)...")
        delete_response = api_client.delete(
            url=f"{api_base_url}/schedule/{schedule_id}",
            headers=learner_headers,
            json={"classroom_id": classroom_id},
            confirmed=True,
        )
        print(
            f"      → DELETE 응답: HTTP {delete_response.status_code} ({'BLOCKED' if _has_permission_error(delete_response) else 'NOT BLOCKED!'})")
        assert _has_permission_error(delete_response), (
            f"[보안 이슈] 학습자 DELETE가 차단되지 않았습니다: {delete_response.status_code}"
        )

        print(f"[5/7] 교육자 - 원본 일정 보존 확인 중...")
        verify_response = api_client.get(
            url=f"{api_base_url}/schedule/{schedule_id}",
            headers=educator_headers,
            params={"classroom_id": classroom_id},
        )
        assert verify_response.status_code == 200, (
            f"[복구 확인 실패] 학습자 DELETE 시도 뒤 원본 일정 조회 실패: {verify_response.status_code}"
        )
        verified = verify_response.json()
        print(f"      → 제목 유지: {verified.get('summary')}")
        print(f"      → 설명 유지: {verified.get('description')}")
        assert verified.get(
            "summary") == original_summary, "[보안 이슈] 학습자 PATCH 시도 뒤 원본 제목이 변경되었습니다."
        assert verified.get(
            "description") == original_description, "[보안 이슈] 학습자 PATCH 시도 뒤 원본 설명이 변경되었습니다."

    finally:
        if schedule_id:
            print(f"[6/7] 교육자 - 임시 일정 삭제 중 (복구)...")
            cleanup_response = api_client.delete(
                url=f"{api_base_url}/schedule/{schedule_id}",
                headers=educator_headers,
                json={"classroom_id": classroom_id},
                confirmed=True,
            )
            print(f"      → 삭제 결과: HTTP {cleanup_response.status_code}")
            assert_http_status(cleanup_response, 200)

            print(f"[7/7] 교육자 - 삭제 후 미조회 확인 중...")
            after_cleanup = api_client.get(
                url=f"{api_base_url}/schedule",
                headers=educator_headers,
                params={
                    "classroom_id": classroom_id,
                    "dt_start_ge": (slot_start - timedelta(hours=1)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "dt_start_le": (slot_end + timedelta(hours=1)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "count": 40,
                },
            )
            assert after_cleanup.status_code == 200, (
                f"[복구 확인 실패] 삭제 후 QA 일정 목록 조회 실패: {after_cleanup.status_code}"
            )
            assert not any(
                item.get("summary") == original_summary
                for item in after_cleanup.json()
            ), "[복구 필요] 삭제 후에도 [QA-AUTO] 임시 일정이 남아 있습니다."
            print(f"      → [QA-AUTO] 임시 일정 미조회 확인 OK")
            print(f"\n[완료] CS-016 테스트 성공! 학습자 권한 차단 및 데이터 복구 완료!")
