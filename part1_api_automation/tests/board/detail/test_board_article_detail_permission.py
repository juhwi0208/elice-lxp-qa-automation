"""게시글 상세 조회 권한 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    article_get_url,
    assert_article_detail_rejected,
    create_article,
    get_article,
    unique_title,
    valid_content,
)
from part1_api_automation.utils import api_client


@pytest.mark.mutating
@pytest.mark.learner
def test_learner_can_get_own_secret_article(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """학습자는 본인이 작성한 비밀글을 조회할 수 있다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("own-secret"),
        "content": valid_content("본인 비밀글 상세 조회"),
        "is_secret": "true",
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
    assert article["is_secret"] is True


@pytest.mark.mutating
@pytest.mark.learner
def test_secret_article_returns_is_secret_true(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """비밀글 상세 조회 결과의 is_secret 값은 true이다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("secret-status"),
        "content": valid_content(),
        "is_secret": "true",
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

    assert article["is_secret"] is True


@pytest.mark.mutating
@pytest.mark.educator
def test_educator_can_get_learner_secret_article(
    api_base_url,
    org_name_short,
    learner_headers,
    educator_headers,
    classroom_id,
    register_created_board_article,
):
    """교육자는 조회 권한이 있는 학습자 비밀글을 조회할 수 있다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("educator-secret"),
        "content": valid_content("교육자 비밀글 조회"),
        "is_secret": "true",
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
        educator_headers,
        board_article_id,
    )

    assert article["id"] == board_article_id
    assert article["is_secret"] is True


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.auth
def test_learner_cannot_get_other_learner_secret_article(
    api_base_url,
    org_name_short,
    learner_headers,
    other_learner_headers,
    classroom_id,
    register_other_learner_board_article,
):
    """다른 학습자가 작성한 비밀글은 조회할 수 없다."""

    # B 학습자가 비밀글을 생성한다.
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("other-learner-secret"),
        "content": valid_content("다른 학습자의 비밀글 상세 조회 제한"),
        "is_secret": "true",
    }

    board_article_id = create_article(
        api_base_url,
        org_name_short,
        other_learner_headers,
        payload,
        register_other_learner_board_article,
    )

    # A 학습자가 B 학습자의 비밀글을 상세 조회한다.
    response = api_client.get(
        article_get_url(api_base_url, org_name_short),
        headers=learner_headers,
        params={
            "board_article_id": board_article_id,
        },
    )

    # 다른 학습자의 비밀글은 권한 부족으로 조회가 거부되어야 한다.
    assert_article_detail_rejected(
        response,
        expected_fail_code="insufficient_permission",
    )


@pytest.mark.mutating
@pytest.mark.learner
def test_learner_can_get_other_learner_article(
    api_base_url,
    org_name_short,
    learner_headers,
    other_learner_headers,
    classroom_id,
    register_other_learner_board_article,
):
    """학습자는 조회 가능한 다른 학습자의 공개 게시글을 정상 조회할 수 있다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("other-learner"),
        "content": valid_content("다른 학습자 공개 게시글 조회"),
        "is_secret": "false",
    }

    board_article_id = create_article(
        api_base_url,
        org_name_short,
        other_learner_headers,
        payload,
        register_other_learner_board_article,
    )

    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        board_article_id,
    )

    assert article["id"] == board_article_id
    assert article["is_secret"] is False
