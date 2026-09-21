"""게시판 글쓰기 API 입력값 및 경계값 검증 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    article_edit_url,
    assert_rejected,
    assert_success,
    get_article,
    multipart,
)
from part1_api_automation.utils import api_client


def _post_article(
    api_base_url,
    org_name_short,
    learner_headers,
    payload,
):
    """게시글 생성 요청을 공통 형식으로 전송한다."""
    return api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=learner_headers,
        files=multipart(payload),
        confirmed=True,
    )


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_title_is_required(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """title 필드가 누락되면 게시글 생성이 실패한다."""
    payload = board_article_payload
    payload.pop("title")

    response = _post_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    assert_rejected(
        response,
        register_created_board_article,
    )


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_empty_title_is_rejected(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """빈 제목으로 게시글을 생성할 수 없다."""
    payload = board_article_payload
    payload["title"] = ""

    response = _post_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    assert_rejected(
        response,
        register_created_board_article,
    )


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_title_accepts_128_characters(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """제목 최대 허용 길이인 128자는 정상 저장된다."""
    payload = board_article_payload
    payload["title"] = "가" * 128

    response = _post_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    body = assert_success(
        response,
        register_created_board_article,
    )

    # 생성 성공뿐 아니라 128자의 제목이 실제 저장됐는지 확인한다.
    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        body["board_article_id"],
    )

    assert article["title"] == "가" * 128


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_title_rejects_129_characters(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """제목 최대 길이인 128자를 초과하면 생성이 실패한다."""
    payload = board_article_payload
    payload["title"] = "가" * 129

    response = _post_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    assert_rejected(
        response,
        register_created_board_article,
    )


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_content_is_required(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """content 필드가 누락되면 게시글 생성이 실패한다."""
    payload = board_article_payload
    payload.pop("content")

    response = _post_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    assert_rejected(
        response,
        register_created_board_article,
    )


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_empty_content_server_behavior(  # BO-007
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """BO-007: 명세상 최소 길이가 없는 빈 content의 실제 서버 정책을 확인한다."""
    payload = board_article_payload
    payload["content"] = ""

    response = _post_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    # TC 자체가 빈 문자열의 서버 검증 여부를 확인하도록 정의되어 있으므로,
    # 성공/실패 어느 응답이든 구조를 검증하고 성공 시 생성 데이터는 정리한다.
    try:
        assert_rejected(
            response,
            register_created_board_article,
        )
    except AssertionError:
        assert_success(
            response,
            register_created_board_article,
        )


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_invalid_is_secret_type_is_rejected(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """boolean으로 변환할 수 없는 is_secret 값은 거부된다."""
    payload = board_article_payload
    payload["is_secret"] = "invalid_boolean_value"

    response = _post_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    assert_rejected(
        response,
        register_created_board_article,
    )


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_nonexistent_course_is_rejected(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """존재하지 않는 course_id를 지정하면 게시글 생성이 실패한다."""
    payload = board_article_payload

    # 일반적인 DB integer 범위 내에서 실제 존재 가능성이 매우 낮은 값을 사용한다.
    payload["course_id"] = 2_147_483_647

    response = _post_article(
        api_base_url,
        org_name_short,
        learner_headers,
        payload,
    )

    assert_rejected(
        response,
        register_created_board_article,
    )
