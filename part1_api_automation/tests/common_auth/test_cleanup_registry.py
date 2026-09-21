"""외부 API 호출 없이 cleanup registry와 게시글 cleanup 등록 동작을 검증한다."""

import pytest

from part1_api_automation.tests.board.helpers import (
    assert_rejected,
    assert_success,
)
from test_support.cleanup import CleanupError, CleanupRegistry


class FakeBoardResponse:
    """게시판 API 응답을 흉내 내는 테스트용 객체."""

    status_code = 200
    text = "response body"

    def __init__(self, body: dict) -> None:
        self._body = body

    def json(self) -> dict:
        return self._body


def test_cleanup_runs_in_reverse_order() -> None:
    """등록된 cleanup 작업은 역순으로 실행된다."""
    calls: list[str] = []
    registry = CleanupRegistry()

    registry.add(
        key="first",
        description="첫 번째",
        callback=lambda: calls.append("first"),
    )
    registry.add(
        key="second",
        description="두 번째",
        callback=lambda: calls.append("second"),
    )

    registry.run()

    assert calls == ["second", "first"]
    assert len(registry) == 0


def test_cleanup_key_is_registered_once() -> None:
    """동일한 key의 cleanup 작업은 중복 등록되지 않는다."""
    calls: list[str] = []
    registry = CleanupRegistry()

    registry.add(
        key="same",
        description="원본",
        callback=lambda: calls.append("first"),
    )
    registry.add(
        key="same",
        description="중복",
        callback=lambda: calls.append("second"),
    )

    registry.run()

    assert calls == ["first"]


def test_cleanup_continues_after_failure_and_reports_all() -> None:
    """한 cleanup이 실패해도 나머지 cleanup 작업은 계속 실행된다."""
    calls: list[str] = []
    registry = CleanupRegistry()

    def fail() -> None:
        calls.append("fail")
        raise RuntimeError("delete failed")

    registry.add(
        key="later",
        description="정상 정리",
        callback=lambda: calls.append("ok"),
    )
    registry.add(
        key="failure",
        description="실패 정리",
        callback=fail,
    )

    with pytest.raises(CleanupError, match="실패 정리"):
        registry.run()

    assert calls == ["fail", "ok"]
    assert len(registry) == 0


def test_created_board_id_is_registered_before_success_assertions() -> None:
    """성공 검증이 실패하더라도 생성된 게시글 ID는 cleanup에 등록된다."""
    registered: list[int] = []

    response = FakeBoardResponse(
        {
            "board_article_id": 101,
            "_result": {
                "status": "fail",
                "status_code": 409,
                "reason": "logic",
            },
        }
    )

    with pytest.raises(AssertionError):
        assert_success(
            response,
            registered.append,
        )

    assert registered == [101]


def test_unexpected_creation_in_rejection_test_is_registered() -> None:
    """실패 TC에서 게시글이 잘못 생성돼도 cleanup 대상으로 등록된다."""
    registered: list[int] = []

    response = FakeBoardResponse(
        {
            "board_article_id": 102,
            "_result": {
                "status": "ok",
                "status_code": 200,
                "reason": None,
            },
        }
    )

    with pytest.raises(AssertionError):
        assert_rejected(
            response,
            registered.append,
        )

    assert registered == [102]
