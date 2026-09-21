"""BO-057~BO-063 게시글 목록 조회 기본/인증/페이지네이션 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    article_list_url,
    create_article,
    get_article,
    get_board_article_list,
    get_postable_board_id,
    unique_title,
    valid_content,
)
from part1_api_automation.utils import api_client
from part1_api_automation.utils.security import mask_sensitive_data


def _request_list(api_base_url, org_name_short, headers, params):
    """게시글 목록 API를 호출한다."""
    return api_client.get(
        article_list_url(api_base_url, org_name_short),
        headers=headers,
        params=params,
    )


def _assert_list_success(response) -> dict:
    """게시글 목록 성공 응답의 공통 구조를 검증한다."""
    assert response.status_code == 200, mask_sensitive_data(response.text)[:500]
    body = response.json()
    assert body.get("_result", {}).get("status") == "ok", mask_sensitive_data(body)
    assert isinstance(body.get("board_article_count"), int), mask_sensitive_data(body)
    assert isinstance(body.get("board_articles"), list), mask_sensitive_data(body)
    return body


@pytest.mark.auth
def test_unauthenticated_article_list_is_rejected(  # BO-057
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
):
    """BO-057: Authorization 헤더 없이 게시글 목록을 조회할 수 없다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    headers = {"x-elice-org-name-short": org_name_short}
    response = _request_list(
        api_base_url,
        org_name_short,
        headers,
        {"board_id": board_id, "offset": 0, "count": 20},
    )

    if response.status_code == 200:
        assert response.json().get("_result", {}).get("status") == "fail"
    else:
        assert 400 <= response.status_code < 500


@pytest.mark.learner
def test_learner_can_get_article_list(  # BO-058
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
):
    """BO-058: 학습자 권한으로 조회 가능한 게시판 목록을 정상 조회한다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    body = get_board_article_list(
        api_base_url, org_name_short, learner_headers, board_id, offset=0, count=20
    )
    assert body["board_article_count"] >= len(body["board_articles"])


@pytest.mark.mutating
@pytest.mark.learner
def test_other_learner_secret_article_is_not_exposed_in_list(  # BO-060
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    other_learner_headers,
    register_created_board_article,
):
    """BO-060: A 학습자가 작성한 비밀글은 B 학습자의 게시글 목록에 노출되지 않는다."""

    # A 학습자와 B 학습자가 공통으로 접근할 수 있는 게시판에서 테스트한다.
    board_id = get_postable_board_id(
        api_base_url,
        org_name_short,
        learner_headers,
        course_id,
    )

    # A 학습자가 비밀글을 생성한다.
    payload = {
        "board_id": board_id,
        "title": unique_title("secret-list-permission"),
        "content": valid_content("다른 학습자의 게시글 목록에 노출되면 안 되는 비밀글"),
        "is_secret": "true",
    }

    article_id = create_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
        register_created_board_article,
    )

    # B 학습자 계정으로 동일 게시판의 목록을 조회한다.
    list_body = get_board_article_list(
        api_base_url,
        org_name_short,
        other_learner_headers,
        board_id,
        offset=0,
        count=20,
    )

    # A 학습자가 작성한 비밀글은 B 학습자의 목록에 포함되지 않아야 한다.
    article_ids = {article.get("id") for article in list_body["board_articles"]}

    assert article_id not in article_ids


@pytest.mark.learner
@pytest.mark.boundary
@pytest.mark.parametrize(
    ("offset", "count"),
    [(-1, 20), (0, 0), (0, 21)],
    ids=["negative-offset", "zero-count", "count-over-20"],
)
def test_invalid_offset_or_count_is_rejected(  # BO-061
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    offset,
    count,
):
    """BO-061: offset>=0, count=1~20 범위를 벗어난 요청은 거부된다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    response = _request_list(
        api_base_url,
        org_name_short,
        learner_headers,
        {"board_id": board_id, "offset": offset, "count": count},
    )
    if response.status_code == 200:
        assert response.json().get("_result", {}).get("status") == "fail"
    else:
        assert 400 <= response.status_code < 500


@pytest.mark.mutating
@pytest.mark.learner
def test_article_list_pagination(  # BO-062
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    register_created_board_article,
):
    """BO-062: offset/count를 바꾸면 서로 다른 페이지가 반환된다."""
    board_id = get_postable_board_id(
        api_base_url,
        org_name_short,
        learner_headers,
        course_id,
    )

    # 페이지네이션 검증에 필요한 최소 게시글 수를 테스트가 직접 준비한다.
    for index in range(2):
        payload = {
            "board_id": board_id,
            "title": unique_title(f"pagination-{index}"),
            "content": valid_content("페이지네이션 검증"),
            "is_secret": "false",
        }

        create_article(
            api_base_url,
            org_name_short,
            learner_headers,
            payload,
            register_created_board_article,
        )

    first = get_board_article_list(
        api_base_url,
        org_name_short,
        learner_headers,
        board_id,
        offset=0,
        count=1,
    )

    second = get_board_article_list(
        api_base_url,
        org_name_short,
        learner_headers,
        board_id,
        offset=1,
        count=1,
    )

    assert len(first["board_articles"]) == 1
    assert len(second["board_articles"]) == 1

    first_id = first["board_articles"][0]["id"]
    second_id = second["board_articles"][0]["id"]

    assert first_id != second_id


@pytest.mark.mutating
@pytest.mark.learner
def test_article_list_and_detail_are_consistent(  # BO-063
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    register_created_board_article,
):
    """BO-063: 목록과 상세의 id/title/is_secret 공통 필드가 일치한다."""
    board_id = get_postable_board_id(
        api_base_url, org_name_short, learner_headers, course_id
    )
    payload = {
        "board_id": board_id,
        "title": unique_title("list-detail-consistency"),
        "content": valid_content(),
        "is_secret": "false",
    }
    article_id = create_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
        register_created_board_article,
    )

    body = get_board_article_list(
        api_base_url, org_name_short, learner_headers, board_id, offset=0, count=20
    )
    list_article = next(
        article for article in body["board_articles"] if article["id"] == article_id
    )
    detail = get_article(api_base_url, org_name_short, learner_headers, article_id)

    assert list_article["id"] == detail["id"]
    assert list_article["title"] == detail["title"]
    assert list_article["is_secret"] == detail["is_secret"]
