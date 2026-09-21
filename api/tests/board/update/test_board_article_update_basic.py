"""BO-039~BO-049 게시글 수정 기본 필드 테스트."""

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


def _edit_article(api_base_url, org_name_short, headers, payload):
    """게시글 수정 요청을 전송한다."""
    return api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=headers,
        files=multipart(payload),
        confirmed=True,
    )


def _assert_edit_success(response, board_article_id: int) -> dict:
    """게시글 수정 성공 응답과 대상 ID를 검증한다."""
    assert response.status_code == 200, mask_sensitive_data(response.text)[:500]
    body = response.json()
    result = body.get("_result", {})
    assert result.get("status") == "ok", mask_sensitive_data(body)
    assert result.get("status_code") == 200, mask_sensitive_data(body)
    assert body.get("board_article_id") == board_article_id, mask_sensitive_data(body)
    return body


def _create_owned_article(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
    *,
    title_prefix: str,
    is_secret: str = "false",
    course_id: int | None = None,
) -> tuple[int, dict]:
    """수정 전제조건으로 사용할 본인 게시글을 생성한다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title(title_prefix),
        "content": valid_content("수정 전 원본 내용"),
        "is_secret": is_secret,
    }
    if course_id is not None:
        payload["course_id"] = course_id

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
def test_owner_can_update_board_article(  # BO-039
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-039: 본인이 작성한 게시글의 필수값을 정상 수정할 수 있다."""
    board_article_id, original = _create_owned_article(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
        title_prefix="update-basic",
    )
    updated = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": unique_title("updated-basic"),
        "content": valid_content("수정된 게시글 내용"),
        "is_secret": "true",
    }

    response = _edit_article(
        api_base_url,
        org_name_short,
        learner_headers,
        updated,
    )
    _assert_edit_success(response, board_article_id)

    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        board_article_id,
    )
    assert article["title"] == updated["title"] != original["title"]
    assert article["content"] == updated["content"]
    assert article["is_secret"] is True


@pytest.mark.mutating
@pytest.mark.learner
def test_article_title_can_be_changed(  # BO-040
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-040: 기존 제목과 다른 제목으로 변경할 수 있다."""
    board_article_id, original = _create_owned_article(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
        title_prefix="update-title",
    )
    changed_title = unique_title("changed-title")
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": changed_title,
        "content": original["content"],
        "is_secret": original["is_secret"],
    }

    response = _edit_article(api_base_url, org_name_short, learner_headers, payload)
    _assert_edit_success(response, board_article_id)

    article = get_article(api_base_url, org_name_short, learner_headers, board_article_id)
    assert article["title"] == changed_title


@pytest.mark.mutating
@pytest.mark.learner
def test_article_title_accepts_128_characters(  # BO-042
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-042: 수정 시 제목은 정확히 128자까지 허용된다."""
    board_article_id, original = _create_owned_article(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
        title_prefix="update-title-128",
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": "가" * 128,
        "content": original["content"],
        "is_secret": original["is_secret"],
    }

    response = _edit_article(api_base_url, org_name_short, learner_headers, payload)
    _assert_edit_success(response, board_article_id)

    article = get_article(api_base_url, org_name_short, learner_headers, board_article_id)
    assert article["title"] == payload["title"]
    assert len(article["title"]) == 128


@pytest.mark.mutating
@pytest.mark.learner
def test_article_content_can_be_changed(  # BO-044
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-044: 게시글 내용을 변경할 수 있다."""
    board_article_id, original = _create_owned_article(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
        title_prefix="update-content",
    )
    changed_content = valid_content("BO-044 변경된 내용")
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": original["title"],
        "content": changed_content,
        "is_secret": original["is_secret"],
    }

    response = _edit_article(api_base_url, org_name_short, learner_headers, payload)
    _assert_edit_success(response, board_article_id)

    article = get_article(api_base_url, org_name_short, learner_headers, board_article_id)
    assert article["content"] == changed_content


@pytest.mark.mutating
@pytest.mark.learner
def test_public_article_can_be_changed_to_secret(  # BO-046
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-046: 공개 게시글을 비밀글로 변경할 수 있다."""
    board_article_id, original = _create_owned_article(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
        title_prefix="public-to-secret",
        is_secret="false",
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": original["title"],
        "content": original["content"],
        "is_secret": "true",
    }

    response = _edit_article(api_base_url, org_name_short, learner_headers, payload)
    _assert_edit_success(response, board_article_id)
    article = get_article(api_base_url, org_name_short, learner_headers, board_article_id)
    assert article["is_secret"] is True


@pytest.mark.mutating
@pytest.mark.learner
def test_secret_article_can_be_changed_to_public(  # BO-047
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-047: 비밀글을 공개 게시글로 변경할 수 있다."""
    board_article_id, original = _create_owned_article(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
        title_prefix="secret-to-public",
        is_secret="true",
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": original["title"],
        "content": original["content"],
        "is_secret": "false",
    }

    response = _edit_article(api_base_url, org_name_short, learner_headers, payload)
    _assert_edit_success(response, board_article_id)
    article = get_article(api_base_url, org_name_short, learner_headers, board_article_id)
    assert article["is_secret"] is False


@pytest.mark.mutating
@pytest.mark.learner
def test_article_course_can_be_changed(  # BO-048
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    course_id,
    register_created_board_article,
):
    """BO-048: 과목 미연결 게시글에 사용 가능한 과목을 연결할 수 있다."""
    board_article_id, original = _create_owned_article(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
        title_prefix="update-course",
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "course_id": course_id,
        "title": original["title"],
        "content": original["content"],
        "is_secret": original["is_secret"],
    }

    response = _edit_article(api_base_url, org_name_short, learner_headers, payload)
    _assert_edit_success(response, board_article_id)
    article = get_article(api_base_url, org_name_short, learner_headers, board_article_id)
    assert article["course_id"] == course_id


@pytest.mark.mutating
@pytest.mark.learner
def test_article_update_without_course_id_succeeds(  # BO-049
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-049: 선택값인 course_id 없이도 게시글 수정이 정상 처리된다."""
    board_article_id, original = _create_owned_article(
        api_base_url,
        org_name_short,
        learner_headers,
        classroom_id,
        register_created_board_article,
        title_prefix="update-no-course",
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": unique_title("updated-no-course"),
        "content": original["content"],
        "is_secret": original["is_secret"],
    }

    response = _edit_article(api_base_url, org_name_short, learner_headers, payload)
    _assert_edit_success(response, board_article_id)
