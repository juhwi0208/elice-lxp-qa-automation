"""BO-041, BO-043, BO-045, BO-055~056 게시글 수정 검증 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    article_edit_url,
    create_article,
    get_article,
    multipart,
    unique_title,
    valid_content,
)
from part1_api_automation.utils import api_client
from part1_api_automation.utils.security import mask_sensitive_data


def _post_edit(api_base_url, org_name_short, headers, payload):
    """수정 API 요청을 전송한다."""
    return api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=headers,
        files=multipart(payload),
        confirmed=True,
    )


def _assert_edit_rejected(response) -> dict | None:
    """수정 요청이 4xx 또는 API 논리 실패로 거부됐는지 확인한다."""
    if response.status_code != 200:
        assert 400 <= response.status_code < 500, mask_sensitive_data(response.text)[
            :500
        ]
        try:
            return response.json()
        except ValueError:
            return None

    body = response.json()
    assert body.get("_result", {}).get("status") == "fail", mask_sensitive_data(body)
    return body


def _create_target(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """실패 후 원본 불변 여부를 확인할 수정 대상 게시글을 만든다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("update-validation"),
        "content": valid_content("수정 검증 원본"),
        "is_secret": "false",
    }
    board_article_id = create_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
        register_created_board_article,
    )
    return board_article_id, payload


@pytest.mark.mutating
@pytest.mark.learner
def test_update_requires_title(  # BO-041
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-041: title 누락 시 수정이 실패하고 기존 제목은 유지된다."""
    board_article_id, original = _create_target(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "content": original["content"],
        "is_secret": original["is_secret"],
    }

    _assert_edit_rejected(
        _post_edit(api_base_url, org_name_short, learner_headers, payload)
    )
    article = get_article(
        api_base_url, org_name_short, learner_headers, board_article_id
    )
    assert article["title"] == original["title"]


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_update_rejects_129_character_title(  # BO-043
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-043: title 최대 길이 128자를 초과하면 수정이 실패한다."""
    board_article_id, original = _create_target(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": "가" * 129,
        "content": original["content"],
        "is_secret": original["is_secret"],
    }

    _assert_edit_rejected(
        _post_edit(api_base_url, org_name_short, learner_headers, payload)
    )
    article = get_article(
        api_base_url, org_name_short, learner_headers, board_article_id
    )
    assert article["title"] == original["title"]


@pytest.mark.mutating
@pytest.mark.learner
def test_update_requires_content(  # BO-045
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-045: content 누락 시 수정이 실패하고 기존 내용은 유지된다."""
    board_article_id, original = _create_target(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": original["title"],
        "is_secret": original["is_secret"],
    }

    _assert_edit_rejected(
        _post_edit(api_base_url, org_name_short, learner_headers, payload)
    )
    article = get_article(
        api_base_url, org_name_short, learner_headers, board_article_id
    )
    assert article["content"] == original["content"]


@pytest.mark.learner
def test_update_nonexistent_article_is_rejected(  # BO-055
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
):
    """BO-055: 존재하지 않는 게시글 ID로 수정할 수 없다."""
    payload = {
        "board_article_id": 2_147_483_647,
        "classroom_id": classroom_id,
        "title": unique_title("nonexistent-update"),
        "content": valid_content(),
        "is_secret": "false",
    }
    _assert_edit_rejected(
        _post_edit(api_base_url, org_name_short, learner_headers, payload)
    )


@pytest.mark.mutating
@pytest.mark.learner
def test_update_non_integer_article_id_is_rejected(  # BO-056
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-056: 정수 형식이 아닌 board_article_id는 검증 오류로 거부된다."""
    payload = {
        "board_article_id": "invalid-id",
        "classroom_id": classroom_id,
        "title": unique_title("invalid-id-update"),
        "content": valid_content(),
        "is_secret": "false",
    }

    response = _post_edit(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    # 비정상적으로 게시글이 생성된 경우에도 테스트 데이터가 남지 않도록 등록한다.
    if response.status_code == 200:
        body = response.json()
        created_board_article_id = body.get("board_article_id")

        if isinstance(created_board_article_id, int):
            register_created_board_article(created_board_article_id)

    _assert_edit_rejected(response)
