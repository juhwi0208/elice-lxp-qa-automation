"""BO-052~BO-054 게시글 수정 인증/권한 테스트."""

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
    """지정한 헤더로 게시글 수정 요청을 전송한다."""
    return api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=headers,
        files=multipart(payload),
        confirmed=True,
    )


def _assert_rejected(response, expected_fail_code: str | None = None):
    """인증/권한 실패 응답을 검증한다."""
    if response.status_code != 200:
        assert 400 <= response.status_code < 500, mask_sensitive_data(response.text)[:500]
        return
    body = response.json()
    assert body.get("_result", {}).get("status") == "fail", mask_sensitive_data(body)
    if expected_fail_code is not None:
        assert body.get("fail_code") == expected_fail_code, mask_sensitive_data(body)


def _payload_for(article_id, classroom_id, title):
    """권한 테스트에서 공통으로 사용할 수정 payload를 만든다."""
    return {
        "board_article_id": article_id,
        "classroom_id": classroom_id,
        "title": title,
        "content": valid_content("권한 테스트 수정 내용"),
        "is_secret": "false",
    }


@pytest.mark.mutating
@pytest.mark.auth
def test_unauthenticated_article_update_is_rejected(  # BO-052
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-052: Authorization 헤더가 없으면 게시글 수정이 거부된다."""
    original = {
        "classroom_id": classroom_id,
        "title": unique_title("unauth-update-target"),
        "content": valid_content(),
        "is_secret": "false",
    }
    article_id = create_article(
        api_base_url, org_name_short, learner_headers, original, register_created_board_article
    )
    headers = {"x-elice-org-name-short": org_name_short}

    response = _post_edit(
        api_base_url,
        org_name_short,
        headers,
        _payload_for(article_id, classroom_id, unique_title("unauth-update")),
    )
    _assert_rejected(response)

    article = get_article(api_base_url, org_name_short, learner_headers, article_id)
    assert article["title"] == original["title"]


@pytest.mark.mutating
@pytest.mark.auth
def test_invalid_sessionkey_article_update_is_rejected(  # BO-053
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-053: 유효하지 않은 sessionkey로는 게시글을 수정할 수 없다."""
    original = {
        "classroom_id": classroom_id,
        "title": unique_title("invalid-session-update-target"),
        "content": valid_content(),
        "is_secret": "false",
    }
    article_id = create_article(
        api_base_url, org_name_short, learner_headers, original, register_created_board_article
    )
    invalid_headers = {
        "Authorization": "Bearer invalid-sessionkey-for-qa",
        "x-elice-org-name-short": org_name_short,
    }

    response = _post_edit(
        api_base_url,
        org_name_short,
        invalid_headers,
        _payload_for(article_id, classroom_id, unique_title("invalid-session-update")),
    )
    _assert_rejected(response)

    article = get_article(api_base_url, org_name_short, learner_headers, article_id)
    assert article["title"] == original["title"]


@pytest.mark.mutating
@pytest.mark.learner
def test_learner_cannot_update_other_learner_article(  # BO-054
    api_base_url,
    org_name_short,
    learner_headers,
    other_learner_headers,
    classroom_id,
    register_other_learner_board_article,
):
    """BO-054: 다른 학습자가 작성한 게시글 수정은 권한 오류로 거부된다."""
    original = {
        "classroom_id": classroom_id,
        "title": unique_title("other-learner-update-target"),
        "content": valid_content(),
        "is_secret": "false",
    }
    article_id = create_article(
        api_base_url,
        org_name_short,
        other_learner_headers,
        original,
        register_other_learner_board_article,
    )

    response = _post_edit(
        api_base_url,
        org_name_short,
        learner_headers,
        _payload_for(article_id, classroom_id, unique_title("unauthorized-update")),
    )
    _assert_rejected(response, expected_fail_code="insufficient_permission")

    article = get_article(api_base_url, org_name_short, other_learner_headers, article_id)
    assert article["title"] == original["title"]
