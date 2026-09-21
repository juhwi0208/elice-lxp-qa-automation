"""클래스 홈 API 검증에 사용하는 공통 fixture."""

import os
from datetime import UTC, datetime, timedelta

import pytest

from part1_api_automation.tests.board.helpers import (
    get_board_article_list,
    get_postable_board_id,
)
from part1_api_automation.utils.course_api import CourseApi


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        pytest.fail(f"{name}은 정수여야 합니다.")
    if parsed <= 0:
        pytest.fail(f"{name}은 양의 정수여야 합니다.")
    return parsed


@pytest.fixture(scope="session")
def schedule_window() -> dict[str, str]:
    """클래스 홈 일정 위젯을 조회할 고정 실행 구간을 반환한다."""
    now = datetime.now(UTC)
    return {
        "dt_start_ge": (now - timedelta(days=30))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "dt_start_le": (now + timedelta(days=30))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }


@pytest.fixture(scope="session")
def learner_course_api(
    classroom_api_base_url: str,
    course_api_base_url: str,
    learner_headers: dict,
) -> CourseApi:
    """학습자 인증으로 클래스 홈의 과목 위젯 API를 호출한다."""
    return CourseApi(
        classroom_base_url=classroom_api_base_url,
        course_base_url=course_api_base_url,
        headers=learner_headers,
    )


@pytest.fixture(scope="session")
def board_article_reference(
    api_base_url: str,
    org_name_short: str,
    learner_headers: dict,
    course_id: int,
) -> dict:
    """게시글 위젯의 목록·상세 연계 검증에 사용할 게시글을 찾는다.

    개인 실행 환경에 ``LXP_BOARD_ARTICLE_ID``가 있으면 해당 게시글을 사용하고,
    없으면 QA 과목의 조회 가능한 게시판에서 첫 게시글을 선택한다. 테스트를 위해
    데이터를 새로 만들지 않으므로 읽기 전용 실행 원칙을 유지한다.
    """
    configured_id = _optional_int("LXP_BOARD_ARTICLE_ID")
    if configured_id is not None:
        return {"id": configured_id, "summary": None}

    board_id = get_postable_board_id(
        api_base_url,
        org_name_short,
        learner_headers,
        course_id,
    )
    body = get_board_article_list(
        api_base_url,
        org_name_short,
        learner_headers,
        board_id,
        offset=0,
        count=20,
    )
    articles = body["board_articles"]
    if not articles:
        pytest.skip("클래스 홈 게시글 위젯과 연계할 기존 게시글이 없습니다.")

    summary = articles[0]
    article_id = summary.get("id", summary.get("board_article_id"))
    if not isinstance(article_id, int) or article_id <= 0:
        pytest.fail("게시글 목록 응답에 유효한 게시글 ID가 없습니다.")

    return {"id": article_id, "summary": summary}
