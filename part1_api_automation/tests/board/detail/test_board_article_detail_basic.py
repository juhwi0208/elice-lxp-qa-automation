"""게시글 목록 및 상세 조회 기본 동작 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    create_article,
    get_article,
    get_board_article_list,
    get_postable_board_id,
    unique_title,
    valid_content,
)


@pytest.mark.mutating
@pytest.mark.learner
def test_board_article_list_is_returned(
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    register_created_board_article,
):
    """게시판의 게시글 목록을 정상적으로 조회할 수 있다."""
    board_id = get_postable_board_id(
        api_base_url,
        org_name_short,
        learner_headers,
        course_id,
    )

    payload = {
        "board_id": board_id,
        "title": unique_title("detail-list"),
        "content": valid_content("게시글 목록 조회 테스트"),
        "is_secret": "false",
    }

    board_article_id = create_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
        register_created_board_article,
    )

    body = get_board_article_list(
        api_base_url,
        org_name_short,
        learner_headers,
        board_id,
        offset=0,
        count=20,
    )

    assert body["board_article_count"] >= 1
    assert any(article["id"] == board_article_id for article in body["board_articles"])


@pytest.mark.mutating
@pytest.mark.learner
def test_board_article_detail_is_returned(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """존재하는 게시글 ID로 상세 정보를 정상 조회할 수 있다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("detail-basic"),
        "content": valid_content("게시글 상세 조회 테스트"),
        "is_secret": "false",
    }

    board_article_id = create_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
        register_created_board_article,
    )

    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        board_article_id,
    )

    assert article["id"] == board_article_id
    assert article["title"] == payload["title"]
    assert article["content"] == payload["content"]


@pytest.mark.mutating
@pytest.mark.learner
def test_learner_can_get_own_article(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """학습자가 자신이 작성한 게시글을 상세 조회할 수 있다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("own-article"),
        "content": valid_content("본인 게시글 조회"),
        "is_secret": "false",
    }

    board_article_id = create_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
        register_created_board_article,
    )

    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        board_article_id,
    )

    assert article["id"] == board_article_id
