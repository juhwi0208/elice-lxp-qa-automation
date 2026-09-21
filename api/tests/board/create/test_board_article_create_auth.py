"""게시판 글쓰기 API 인증 실패 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    article_edit_url,
    assert_rejected,
    multipart,
)
from part1_api_automation.utils import api_client


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.auth
def test_unauthenticated_article_creation_is_rejected(
    api_base_url,
    org_name_short,
    board_article_payload,
    register_created_board_article,
):
    """Authorization 헤더가 없으면 게시글 생성이 실패한다."""
    # 미인증 요청을 검증하기 위해 Authorization 헤더를 포함하지 않는다.
    headers = {
        "x-elice-org-name-short": org_name_short,
    }

    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=headers,
        files=multipart(board_article_payload),
        confirmed=True,
    )

    assert_rejected(
        response,
        register_created_board_article,
    )


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.auth
def test_invalid_sessionkey_article_creation_is_rejected(
    api_base_url,
    org_name_short,
    board_article_payload,
    register_created_board_article,
):
    """유효하지 않은 sessionkey로 게시글을 생성할 수 없다."""
    # 실제 인증정보 대신 테스트용 유효하지 않은 sessionkey를 사용한다.
    headers = {
        "Authorization": "Bearer invalid-sessionkey-for-api-test",
        "x-elice-org-name-short": org_name_short,
    }

    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=headers,
        files=multipart(board_article_payload),
        confirmed=True,
    )

    assert_rejected(
        response,
        register_created_board_article,
    )
