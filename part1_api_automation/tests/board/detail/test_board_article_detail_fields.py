"""게시글 상세 조회 응답 필드 테스트."""

import tempfile

import pytest

from part1_api_automation.tests.board.helpers import (
    create_article,
    get_article,
    unique_title,
    valid_content,
)


@pytest.mark.mutating
@pytest.mark.learner
def test_article_title_is_returned(  # BO-027
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-027: 작성된 제목이 상세 조회 결과에 그대로 반환된다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("detail-title"),
        "content": valid_content("제목 상세 조회 검증"),
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

    assert article["title"] == payload["title"]


@pytest.mark.mutating
@pytest.mark.learner
def test_article_content_is_returned(  # BO-028
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-028: 작성된 내용이 상세 조회 결과에 그대로 반환된다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("detail-content"),
        "content": valid_content("내용 상세 조회 검증"),
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

    assert article["content"] == payload["content"]


@pytest.mark.mutating
@pytest.mark.learner
def test_article_author_information_is_returned(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """게시글 상세 조회 시 작성자 정보가 반환된다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("author"),
        "content": valid_content(),
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

    user = article["user"]

    assert isinstance(user["id"], int)
    assert "firstname" in user
    assert "lastname" in user
    assert "fullname" in user
    assert "email" in user


@pytest.mark.mutating
@pytest.mark.learner
def test_article_created_datetime_is_returned(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """게시글 작성 시간이 상세 조회 결과에 반환된다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("created-time"),
        "content": valid_content(),
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

    assert isinstance(article["created_datetime"], int)
    assert article["created_datetime"] > 0


@pytest.mark.mutating
@pytest.mark.learner
def test_article_course_id_is_returned(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    course_id,
    register_created_board_article,
):
    """연결 과목이 지정된 게시글의 course_id가 정상 반환된다."""
    payload = {
        "classroom_id": classroom_id,
        "course_id": course_id,
        "title": unique_title("with-course"),
        "content": valid_content(),
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

    assert article["course_id"] == course_id


@pytest.mark.mutating
@pytest.mark.learner
def test_article_without_course_returns_null_course_id(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """연결 과목이 없는 게시글은 course_id가 null로 반환된다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("without-course"),
        "content": valid_content(),
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

    assert article["course_id"] is None


@pytest.mark.mutating
@pytest.mark.learner
def test_article_attachment_information_is_returned(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """첨부파일이 있는 게시글은 첨부파일 상세 정보가 반환된다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("detail-attachment"),
        "content": valid_content(),
        "is_secret": "false",
    }

    filename = "detail_attachment_test.txt"

    with tempfile.TemporaryFile() as file_obj:
        file_obj.write(b"board article detail attachment")
        file_obj.seek(0)

        board_article_id = create_article(
            api_base_url,
            org_name_short,
            learner_headers,
            payload,
            register_created_board_article,
            attachments=[
                (
                    filename,
                    file_obj,
                    "text/plain",
                )
            ],
        )

    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        board_article_id,
    )

    attachments = article["article_attachments"]

    assert len(attachments) == 1

    attachment_item = attachments[0]
    attachment = attachment_item["attachment"]

    assert isinstance(attachment_item["id"], int)
    assert attachment["filename"] == filename
    assert attachment["filesize"] > 0
    assert isinstance(attachment["url"], str)
    assert attachment["url"]


@pytest.mark.mutating
@pytest.mark.learner
def test_article_without_attachment_returns_empty_list(
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """첨부파일이 없는 게시글은 article_attachments가 빈 목록이다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("no-detail-attachment"),
        "content": valid_content(),
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

    assert article["article_attachments"] == []
