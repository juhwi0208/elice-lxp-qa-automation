"""BO-064~BO-068 게시글 목록 제목 검색 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    article_list_url,
    create_article,
    get_postable_board_id,
    unique_title,
    valid_content,
)
from part1_api_automation.utils import api_client
from part1_api_automation.utils.security import mask_sensitive_data


def _search(api_base_url, org_name_short, headers, board_id, filter_title):
    """filter_title 조건으로 게시글 목록을 검색한다."""
    return api_client.get(
        article_list_url(api_base_url, org_name_short),
        headers=headers,
        params={
            "board_id": board_id,
            "filter_title": filter_title,
            "offset": 0,
            "count": 20,
        },
    )


def _assert_search_success(response) -> dict:
    """검색 성공 응답을 검증한다."""
    assert response.status_code == 200, mask_sensitive_data(response.text)[:500]
    body = response.json()
    assert body.get("_result", {}).get("status") == "ok", mask_sensitive_data(body)
    return body


def _create_search_article(
    api_base_url,
    org_name_short,
    learner_headers,
    board_id,
    register_created_board_article,
    title,
):
    """검색 결과에 반드시 포함될 QA 게시글을 만든다."""
    payload = {
        "board_id": board_id,
        "title": title,
        "content": valid_content("목록 검색 테스트"),
        "is_secret": "false",
    }
    return create_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
        register_created_board_article,
    )


@pytest.mark.mutating
@pytest.mark.learner
def test_title_partial_match_search(  # BO-064
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    register_created_board_article,
):
    """BO-064: 제목 일부 문자열로 검색하면 해당 게시글이 반환된다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    title = unique_title("partial-search-keyword")
    article_id = _create_search_article(
        api_base_url,
        org_name_short,
        learner_headers,
        board_id,
        register_created_board_article,
        title,
    )
    keyword = "partial-search-keyword"
    filter_title = f"%{keyword}%"

    body = _assert_search_success(
        _search(
            api_base_url,
            org_name_short,
            learner_headers,
            board_id,
            filter_title,
        )
    )
    assert any(article["id"] == article_id for article in body["board_articles"])
    assert all(keyword in article["title"] for article in body["board_articles"])


@pytest.mark.mutating
@pytest.mark.learner
def test_title_exact_match_search(  # BO-065
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    register_created_board_article,
):
    """BO-065: 제목 전체 문자열을 검색하면 해당 게시글이 반환된다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    title = unique_title("exact-search")
    article_id = _create_search_article(
        api_base_url,
        org_name_short,
        learner_headers,
        board_id,
        register_created_board_article,
        title,
    )

    body = _assert_search_success(
        _search(api_base_url, org_name_short, learner_headers, board_id, title)
    )
    assert any(
        article["id"] == article_id and article["title"] == title
        for article in body["board_articles"]
    )


@pytest.mark.mutating
@pytest.mark.learner
def test_title_search_with_spaces(  # BO-066
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    register_created_board_article,
):
    """BO-066: 공백을 포함한 검색어도 그대로 검색 조건으로 적용된다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    keyword = "공백 포함 검색"
    title = unique_title(keyword)
    article_id = _create_search_article(
        api_base_url,
        org_name_short,
        learner_headers,
        board_id,
        register_created_board_article,
        title,
    )

    body = _assert_search_success(
        _search(api_base_url, org_name_short, learner_headers, board_id, f"%{keyword}%")
    )
    assert any(article["id"] == article_id for article in body["board_articles"])


@pytest.mark.learner
def test_title_search_without_result_returns_empty_list(  # BO-067
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
):
    """BO-067: 존재하지 않는 고유 검색어는 빈 목록을 반환한다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    keyword = unique_title("no-search-result")
    body = _assert_search_success(
        _search(api_base_url, org_name_short, learner_headers, board_id, keyword)
    )
    assert body["board_articles"] == []


@pytest.mark.learner
def test_empty_title_filter_is_rejected(  # BO-068
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
):
    """BO-068: 최소 1자 조건을 위반한 빈 filter_title은 거부된다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    response = _search(api_base_url, org_name_short, learner_headers, board_id, "")

    if response.status_code == 200:
        assert response.json().get("_result", {}).get("status") == "fail"
    else:
        assert 400 <= response.status_code < 500
