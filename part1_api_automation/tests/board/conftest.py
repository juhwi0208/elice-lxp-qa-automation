"""게시판 생성 테스트 전용 데이터 정리 fixture."""

from __future__ import annotations

import os
from collections.abc import Callable
from urllib.parse import quote

import pytest

from part1_api_automation.tests.board.helpers import default_payload, multipart
from part1_api_automation.utils import api_client
from part1_api_automation.utils.response import (
    assert_api_success,
    assert_error_response,
    logic_error,
)
from test_support.cleanup import CleanupRegistry


def _article_delete_url(
    api_base_url: str,
    org_name_short: str,
) -> str:
    """게시글 삭제 API URL을 반환한다."""
    path = os.getenv(
        "LXP_BOARD_ARTICLE_DELETE_PATH",
        "/org/{org}/board/article/delete/",
    ).strip()

    encoded_org = quote(org_name_short, safe="")
    resolved_path = path.format(org=encoded_org)

    return f"{api_base_url.rstrip('/')}/{resolved_path.lstrip('/')}"


def _article_get_url(
    api_base_url: str,
    org_name_short: str,
) -> str:
    """게시글 상세 조회 API URL을 반환한다."""
    encoded_org = quote(org_name_short, safe="")
    return f"{api_base_url.rstrip('/')}/org/{encoded_org}/board/article/get/"


def _assert_cleanup_success(
    response,
    board_article_id: int,
) -> None:
    """게시글 삭제 API가 정상 처리됐는지 검증한다."""
    try:
        assert_api_success(response)
    except AssertionError as exc:
        raise AssertionError(f"게시글 {board_article_id} 삭제 실패: {exc}") from exc


def _assert_article_deleted(
    response,
    board_article_id: int,
) -> None:
    """삭제 후 상세 조회에서 게시글이 존재하지 않는지 검증한다.

    게시판 상세 조회 API는 존재하지 않는 게시글 조회 시
    HTTP 404가 아니라 HTTP 200 응답과 함께
    API 내부 오류 코드 resource_not_found를 반환한다.
    """
    try:
        assert_error_response(
            response,
            logic_error(
                400,
                error_code="resource_not_found",
            ),
        )
    except AssertionError as exc:
        raise AssertionError(
            f"게시글 {board_article_id} 삭제 검증 실패: "
            "삭제 후 상세 조회에서 "
            "resource_not_found 응답이 반환되지 않았습니다. "
            f"{exc}"
        ) from exc


def _register_board_article_cleanup(
    *,
    cleanup_registry: CleanupRegistry,
    api_base_url: str,
    org_name_short: str,
    headers: dict,
    owner_key: str,
) -> Callable[[int], None]:
    """지정한 계정으로 게시글 cleanup을 수행하는 등록 함수를 만든다."""

    delete_url = _article_delete_url(
        api_base_url,
        org_name_short,
    )
    get_url = _article_get_url(
        api_base_url,
        org_name_short,
    )

    def register(board_article_id: int) -> None:
        """생성된 게시글 ID를 cleanup 대상으로 등록한다."""
        if not isinstance(board_article_id, int) or board_article_id <= 0:
            raise ValueError("정리할 board_article_id는 양의 정수여야 합니다.")

        def delete_and_verify() -> None:
            """게시글을 삭제하고 실제 삭제 여부까지 검증한다."""
            delete_response = api_client.post(
                delete_url,
                headers=headers,
                files=multipart(
                    {
                        "board_article_id": board_article_id,
                    }
                ),
                confirmed=True,
            )

            _assert_cleanup_success(
                delete_response,
                board_article_id,
            )

            verify_response = api_client.get(
                get_url,
                headers=headers,
                params={
                    "board_article_id": board_article_id,
                },
            )

            _assert_article_deleted(
                verify_response,
                board_article_id,
            )

        cleanup_registry.add(
            key=f"board-article:{owner_key}:{board_article_id}",
            description=f"{owner_key} 게시글 {board_article_id} 삭제",
            callback=delete_and_verify,
        )

    return register


@pytest.fixture
def register_created_board_article(
    cleanup_registry: CleanupRegistry,
    api_base_url: str,
    org_name_short: str,
    learner_headers: dict,
) -> Callable[[int], None]:
    """기본 학습자가 생성한 게시글을 cleanup 대상으로 등록한다."""
    return _register_board_article_cleanup(
        cleanup_registry=cleanup_registry,
        api_base_url=api_base_url,
        org_name_short=org_name_short,
        headers=learner_headers,
        owner_key="learner-a",
    )


@pytest.fixture
def register_other_learner_board_article(
    cleanup_registry: CleanupRegistry,
    api_base_url: str,
    org_name_short: str,
    other_learner_headers: dict,
) -> Callable[[int], None]:
    """두 번째 학습자가 생성한 게시글을 cleanup 대상으로 등록한다."""
    return _register_board_article_cleanup(
        cleanup_registry=cleanup_registry,
        api_base_url=api_base_url,
        org_name_short=org_name_short,
        headers=other_learner_headers,
        owner_key="learner-b",
    )


@pytest.fixture
def board_article_payload(
    classroom_id: str,
) -> dict:
    """게시글 생성 테스트에서 사용하는 기본 payload."""
    return default_payload(classroom_id)
