import uuid
from datetime import UTC, datetime, timedelta

import pytest

from part1_api_automation.utils import api_client
from part1_api_automation.utils.config import is_mutating_test_allowed
from part1_api_automation.utils.response import assert_http_status


def _fmt(value: datetime) -> str:
    """datetime을 API 요청 형식 문자열로 변환한다."""
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture(scope="session")
def api_base_url(classroom_api_base_url) -> str:
    """수업 일정 API는 classroom-api 서비스를 사용하므로 classroom_api_base_url을 사용한다."""
    return classroom_api_base_url


@pytest.fixture
def qa_schedule(api_base_url, classroom_id, educator_headers):
    """
    class_schedule 테스트 전역에서 사용할 공용 QA 임시 일정을 생성하고 삭제한다.
    
    - yield 전: 교육자 권한으로 임시 일정 1건 생성
    - yield 값: dict(id, summary, start_at, end_at)
    - yield 후: 교육자 권한으로 해당 일정 삭제 (성공/실패 무관)
    """
    if not is_mutating_test_allowed():
        pytest.skip("데이터 생성이 필요한 테스트는 상태 변경이 허용된 환경에서만 실행됩니다.")

    start_at = (datetime.now(UTC) + timedelta(days=7)).replace(
        hour=2, minute=0, second=0, microsecond=0
    )
    end_at = start_at + timedelta(hours=1)
    summary = f"[QA-AUTO] shared-fixture-{uuid.uuid4().hex[:8]}"

    # 생성
    create_response = api_client.post(
        url=f"{api_base_url}/schedule",
        headers=educator_headers,
        json={
            "classroom_id": classroom_id,
            "summary": summary,
            "description": "QA 공통 읽기/쓰기 테스트용 임시 일정",
            "dt_start": _fmt(start_at),
            "dt_end": _fmt(end_at),
        },
        confirmed=True,
    )
    assert_http_status(create_response, 200)

    find_response = api_client.get(
        url=f"{api_base_url}/schedule",
        headers=educator_headers,
        params={
            "classroom_id": classroom_id,
            "dt_start_ge": _fmt(start_at - timedelta(days=1)),
            "dt_start_le": _fmt(end_at + timedelta(days=1)),
            "count": 40,
        },
    )
    assert find_response.status_code == 200
    matches = [i for i in find_response.json() if i.get("summary") == summary]
    assert len(matches) == 1
    schedule_id = matches[0]["id"]

    yield {"id": schedule_id, "summary": summary, "start_at": start_at, "end_at": end_at}

    # 복구
    api_client.delete(
        url=f"{api_base_url}/schedule/{schedule_id}",
        headers=educator_headers,
        json={"classroom_id": classroom_id},
        confirmed=True,
    )
