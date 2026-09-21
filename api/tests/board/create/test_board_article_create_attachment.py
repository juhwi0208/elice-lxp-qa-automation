"""게시판 글쓰기 API 첨부파일 테스트."""

import tempfile

import pytest

from part1_api_automation.tests.board.helpers import (
    FILE_SIZE_LIMIT,
    article_edit_url,
    assert_rejected,
    assert_success,
    get_article,
    multipart,
    unique_title,
    valid_content,
)
from part1_api_automation.utils import api_client


@pytest.mark.mutating
@pytest.mark.learner
def test_create_article_without_attachment(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """첨부파일 없이 게시글을 정상 생성할 수 있다."""
    payload = board_article_payload
    payload["title"] = unique_title("no-attachment")

    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=learner_headers,
        files=multipart(payload),
        confirmed=True,
    )

    body = assert_success(response, register_created_board_article)

    # 생성 후 상세 조회하여 첨부파일이 없는 상태로 저장됐는지 확인한다.
    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        body["board_article_id"],
    )

    assert article["article_attachments"] == []


@pytest.mark.mutating
@pytest.mark.learner
def test_create_article_with_attachment(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """파일을 첨부하면 게시글의 첨부파일 정보에 정상 반영된다."""
    payload = board_article_payload
    payload["title"] = unique_title("attachment")
    filename = "api_board_test.txt"

    # 실제 디스크 파일을 남기지 않는 임시 파일로 첨부 요청을 생성한다.
    with tempfile.TemporaryFile() as file_obj:
        file_obj.write(b"board article attachment test")
        file_obj.seek(0)

        response = api_client.post(
            article_edit_url(api_base_url, org_name_short),
            headers=learner_headers,
            files=multipart(
                payload,
                attachments=[(filename, file_obj, "text/plain")],
            ),
            confirmed=True,
        )

    body = assert_success(response, register_created_board_article)

    article = get_article(
        api_base_url,
        org_name_short,
        learner_headers,
        body["board_article_id"],
    )
    attachments = article["article_attachments"]

    assert len(attachments) == 1
    assert attachments[0]["attachment"]["filename"] == filename
    assert attachments[0]["attachment"]["filesize"] > 0


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_attachment_over_30mb_is_rejected(
    api_base_url,
    org_name_short,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """첨부파일 크기 제한을 1바이트 초과하면 게시글 생성이 실패한다."""
    payload = board_article_payload
    payload["title"] = unique_title("oversized-attachment")

    with tempfile.TemporaryFile() as file_obj:
        # 허용 최대 크기보다 정확히 1바이트 큰 파일을 생성한다.
        file_obj.seek(FILE_SIZE_LIMIT)
        file_obj.write(b"\0")
        file_obj.seek(0)

        response = api_client.post(
            article_edit_url(api_base_url, org_name_short),
            headers=learner_headers,
            files=multipart(
                payload,
                attachments=[("oversized.bin", file_obj, "application/octet-stream")],
            ),
            confirmed=True,
        )

    assert_rejected(response, register_created_board_article)


@pytest.mark.mutating
@pytest.mark.learner
def test_create_article_with_all_supported_fields_and_attachment(
    api_base_url,
    org_name_short,
    course_id,
    learner_headers,
    board_article_payload,
    register_created_board_article,
):
    """모든 지원 필드와 첨부파일을 함께 입력하면 정상 저장된다."""
    payload = board_article_payload
    payload.update(
        {
            "title": unique_title("all-fields-with-attachment"),
            "content": valid_content("모든 필드 입력 검증"),
            "is_secret": "true",
            "course_id": course_id,
        }
    )
    filename = "all_fields_test.txt"

    with tempfile.TemporaryFile() as file_obj:
        file_obj.write(b"all fields attachment")
        file_obj.seek(0)

        response = api_client.post(
            article_edit_url(api_base_url, org_name_short),
            headers=learner_headers,
            files=multipart(
                payload,
                attachments=[(filename, file_obj, "text/plain")],
            ),
            confirmed=True,
        )

    body = assert_success(response, register_created_board_article)

    # 상세 조회를 통해 일반 필드와 첨부파일이 모두 저장됐는지 검증한다.
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

    attachments = article["article_attachments"]

    assert len(attachments) == 1
    assert attachments[0]["attachment"]["filename"] == filename
