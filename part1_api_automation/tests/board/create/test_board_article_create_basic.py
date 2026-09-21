"""게시판 글쓰기 API 정상 생성 시나리오 테스트."""

import pytest

from part1_api_automation.tests.board.helpers import (
    article_edit_url,
    assert_success,
    get_article,
    multipart,
    unique_title,
    valid_content,
)
from part1_api_automation.utils import api_client


@pytest.mark.mutating
@pytest.mark.learner
def test_create_board_article_with_required_fields(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """필수 필드만 입력하면 게시글이 정상 생성된다."""
    payload = board_article_payload

    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=learner_headers,
        files=multipart(payload),
        confirmed=True,
    )

    body = assert_success(response, register_created_board_article)

    # 생성된 게시글을 상세 조회하여 요청한 값이 실제 저장됐는지 확인한다.
    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        body["board_article_id"],
    )

    assert article["title"] == payload["title"]
    assert article["content"] == payload["content"]
    assert article["is_secret"] is False


@pytest.mark.mutating
@pytest.mark.learner
def test_create_secret_board_article(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """is_secret=true로 게시글을 생성하면 비밀글로 저장된다."""
    payload = board_article_payload
    payload["title"] = unique_title("secret")
    payload["is_secret"] = "true"

    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=learner_headers,
        files=multipart(payload),
        confirmed=True,
    )

    body = assert_success(response, register_created_board_article)
    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        body["board_article_id"],
    )

    assert article["is_secret"] is True


@pytest.mark.mutating
@pytest.mark.learner
def test_create_public_board_article(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """is_secret=false로 게시글을 생성하면 공개글로 저장된다."""
    payload = board_article_payload
    payload["title"] = unique_title("public")
    payload["is_secret"] = "false"

    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=learner_headers,
        files=multipart(payload),
        confirmed=True,
    )

    body = assert_success(response, register_created_board_article)
    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        body["board_article_id"],
    )

    assert article["is_secret"] is False


@pytest.mark.mutating
@pytest.mark.learner
def test_create_article_without_optional_fields(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """연결 과목과 첨부파일 없이 게시글을 생성할 수 있다."""
    payload = board_article_payload

    # 기본 payload에는 선택값인 course_id가 포함되지 않는다.
    assert "course_id" not in payload

    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=learner_headers,
        files=multipart(payload),
        confirmed=True,
    )

    assert_success(
        response,
        register_created_board_article,
    )


@pytest.mark.mutating
@pytest.mark.learner
def test_create_article_with_all_supported_fields(
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """모든 일반 필드를 입력하면 요청한 값으로 정상 저장된다."""
    payload = board_article_payload
    payload.update(
        {
            "title": unique_title("all-fields"),
            "content": valid_content("모든 일반 필드 입력 검증"),
            "is_secret": "true",
            "course_id": course_id,
        }
    )

    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=learner_headers,
        files=multipart(payload),
        confirmed=True,
    )

    body = assert_success(response, register_created_board_article)

    # 정상 응답뿐 아니라 각 필드가 실제 게시글에 반영됐는지 검증한다.
    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        body["board_article_id"],
    )

    assert article["title"] == payload["title"]
    assert article["content"] == payload["content"]
    assert article["is_secret"] is True
    assert article["course_id"] == course_id
