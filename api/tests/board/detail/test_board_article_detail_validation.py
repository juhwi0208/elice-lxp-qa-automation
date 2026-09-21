"""게시글 상세 조회 인증 및 입력값 예외 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    article_get_url,
    assert_article_detail_rejected,
)
from part1_api_automation.utils import api_client


@pytest.mark.auth
def test_unauthenticated_article_detail_is_rejected(
    api_base_url,
    org_name_short,
):
    """Authorization 헤더가 없으면 게시글 상세 조회가 거부된다."""
    headers = {
        "x-elice-org-name-short": org_name_short,
    }

    response = api_client.get(
        article_get_url(api_base_url, org_name_short),
        headers=headers,
        params={
            "board_article_id": 1,
        },
    )

    assert_article_detail_rejected(response)


@pytest.mark.learner
def test_nonexistent_article_is_rejected(
    api_base_url,
    org_name_short,
    learner_headers,
):
    """존재하지 않는 게시글 ID를 조회하면 게시글 정보가 반환되지 않는다."""
    nonexistent_id = 2_147_483_647

    response = api_client.get(
        article_get_url(api_base_url, org_name_short),
        headers=learner_headers,
        params={
            "board_article_id": nonexistent_id,
        },
    )

    body = assert_article_detail_rejected(response)

    if body is not None:
        assert "board_article" not in body


@pytest.mark.learner
def test_non_integer_article_id_is_rejected(
    api_base_url,
    org_name_short,
    learner_headers,
):
    """board_article_id가 정수 형식이 아니면 요청이 거부된다."""
    response = api_client.get(
        article_get_url(api_base_url, org_name_short),
        headers=learner_headers,
        params={
            "board_article_id": "invalid-id",
        },
    )

    assert_article_detail_rejected(response)
