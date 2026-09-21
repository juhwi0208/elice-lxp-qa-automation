"""BO-069~BO-072 게시글 목록 정렬 및 검색+정렬 테스트."""

import json

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


def _request_sorted_list(
    api_base_url,
    org_name_short,
    headers,
    board_id,
    *,
    order: str,
    filter_title: str | None = None,
):
    """created_datetime 기준 정렬 조건을 JSON 문자열로 전달한다."""
    params = {
        "board_id": board_id,
        "offset": 0,
        "count": 20,
        "sort_by": json.dumps({"key": "created_datetime", "order": order}),
    }
    if filter_title is not None:
        params["filter_title"] = filter_title

    return api_client.get(
        article_list_url(api_base_url, org_name_short),
        headers=headers,
        params=params,
    )


def _success_body(response) -> dict:
    """정렬 목록 성공 응답을 검증한다."""
    assert response.status_code == 200, mask_sensitive_data(response.text)[:500]
    body = response.json()
    assert body.get("_result", {}).get("status") == "ok", mask_sensitive_data(body)
    return body


def _created_datetimes(body: dict) -> list[int]:
    """목록에서 created_datetime 정수 값만 순서대로 추출한다."""
    values = [article.get("created_datetime") for article in body["board_articles"]]
    assert all(isinstance(value, int) for value in values), mask_sensitive_data(body)
    return values


@pytest.mark.learner
def test_article_list_is_sorted_newest_first(  # BO-069
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
):
    """BO-069: created_datetime desc 조건은 최신순으로 정렬한다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    body = _success_body(
        _request_sorted_list(
            api_base_url, org_name_short, learner_headers, board_id, order="desc"
        )
    )
    if len(body["board_articles"]) < 2:
        pytest.skip("정렬 검증에 필요한 게시글이 2개 이상 없습니다.")
    values = _created_datetimes(body)
    assert values == sorted(values, reverse=True)


@pytest.mark.learner
def test_article_list_is_sorted_oldest_first(  # BO-070
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
):
    """BO-070: created_datetime asc 조건은 작성순으로 정렬한다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    body = _success_body(
        _request_sorted_list(
            api_base_url, org_name_short, learner_headers, board_id, order="asc"
        )
    )
    if len(body["board_articles"]) < 2:
        pytest.skip("정렬 검증에 필요한 게시글이 2개 이상 없습니다.")
    values = _created_datetimes(body)
    assert values == sorted(values)


@pytest.mark.learner
@pytest.mark.parametrize(
    "sort_by",
    [
        {"key": "unsupported", "order": "desc"},
        {"key": "created_datetime", "order": "unsupported"},
    ],
    ids=["unsupported-key", "unsupported-order"],
)
def test_invalid_sort_condition_is_rejected(  # BO-071
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    sort_by,
):
    """BO-071: 명세에 없는 sort_by key/order는 JSON Schema 검증에서 거부된다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    response = api_client.get(
        article_list_url(api_base_url, org_name_short),
        headers=learner_headers,
        params={
            "board_id": board_id,
            "offset": 0,
            "count": 20,
            "sort_by": json.dumps(sort_by),
        },
    )

    if response.status_code == 200:
        assert response.json().get("_result", {}).get("status") == "fail"
    else:
        assert 400 <= response.status_code < 500


@pytest.mark.mutating
@pytest.mark.learner
def test_title_search_results_are_sorted_newest_first(  # BO-072
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    register_created_board_article,
):
    """BO-072: 제목 검색 조건과 최신순 정렬 조건을 함께 적용할 수 있다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    keyword = unique_title("combined-search-sort")

    # 같은 검색어를 공유하는 게시글 두 건을 생성해 검색+정렬 전제조건을 만든다.
    for suffix in ("first", "second"):
        payload = {
            "board_id": board_id,
            "title": f"{keyword} {suffix}",
            "content": valid_content(f"검색+정렬 {suffix}"),
            "is_secret": "false",
        }
        create_article(
            api_base_url,
            org_name_short,
            learner_headers,
            payload,
            register_created_board_article,
        )

    body = _success_body(
        _request_sorted_list(
            api_base_url,
            org_name_short,
            learner_headers,
            board_id,
            order="desc",
            filter_title=f"%{keyword}%",
        )
    )
    assert len(body["board_articles"]) >= 2
    assert all(keyword in article["title"] for article in body["board_articles"])
    values = _created_datetimes(body)
    assert values == sorted(values, reverse=True)
