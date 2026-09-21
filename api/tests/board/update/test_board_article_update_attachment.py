"""BO-050~BO-051 게시글 수정 첨부파일 테스트."""

import tempfile

import pytest

from part1_api_automation.tests.board.helpers import (
    FILE_SIZE_LIMIT,
    article_edit_url,
    create_article,
    get_article,
    multipart,
    unique_title,
    valid_content,
)
from part1_api_automation.utils import api_client
from part1_api_automation.utils.security import mask_sensitive_data


def _create_target(api_base_url, org_name_short, learner_headers, classroom_id, register_created_board_article):
    """첨부파일 수정 테스트용 게시글을 생성한다."""
    payload = {
        "classroom_id": classroom_id,
        "title": unique_title("update-attachment"),
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
    return article_id, payload


def _post_with_attachment(api_base_url, org_name_short, headers, payload, attachment):
    """첨부파일을 포함한 수정 요청을 전송한다."""
    return api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=headers,
        files=multipart(payload, attachments=[attachment]),
        confirmed=True,
    )


@pytest.mark.mutating
@pytest.mark.learner
def test_attachment_can_be_added_when_updating_article(  # BO-050
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-050: 기존 게시글 수정 시 파일을 추가할 수 있다."""
    board_article_id, original = _create_target(
        api_base_url, org_name_short, learner_headers, classroom_id, register_created_board_article
    )
    filename = "bo050_update_attachment.txt"
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": original["title"],
        "content": original["content"],
        "is_secret": original["is_secret"],
    }

    with tempfile.TemporaryFile() as file_obj:
        file_obj.write(b"BO-050 update attachment")
        file_obj.seek(0)
        response = _post_with_attachment(
            api_base_url,
            org_name_short,
            learner_headers,
            payload,
            (filename, file_obj, "text/plain"),
        )

    assert response.status_code == 200, mask_sensitive_data(response.text)[:500]
    body = response.json()
    assert body.get("_result", {}).get("status") == "ok", mask_sensitive_data(body)

    article = get_article(api_base_url, org_name_short, learner_headers, board_article_id)
    filenames = [item["attachment"]["filename"] for item in article["article_attachments"]]
    assert filename in filenames


@pytest.mark.mutating
@pytest.mark.learner
@pytest.mark.boundary
def test_update_rejects_attachment_over_30mb(  # BO-051
    api_base_url,
    org_name_short,
    learner_headers,
    classroom_id,
    register_created_board_article,
):
    """BO-051: 30MB 제한을 1 byte라도 초과한 첨부파일은 거부된다."""
    board_article_id, original = _create_target(
        api_base_url, org_name_short, learner_headers, classroom_id, register_created_board_article
    )
    payload = {
        "board_article_id": board_article_id,
        "classroom_id": classroom_id,
        "title": original["title"],
        "content": original["content"],
        "is_secret": original["is_secret"],
    }

    # 메모리에 30MB 전체를 올리지 않고 임시 파일 크기만 확장한다.
    with tempfile.TemporaryFile() as file_obj:
        file_obj.truncate(FILE_SIZE_LIMIT + 1)
        file_obj.seek(0)
        response = _post_with_attachment(
            api_base_url,
            org_name_short,
            learner_headers,
            payload,
            ("bo051_over_limit.bin", file_obj, "application/octet-stream"),
        )

    if response.status_code == 200:
        body = response.json()
        assert body.get("_result", {}).get("status") == "fail", mask_sensitive_data(body)
    else:
        assert 400 <= response.status_code < 500, mask_sensitive_data(response.text)[:500]

    # 실패한 수정이 원본 게시글 자체를 손상시키지 않았는지도 확인한다.
    article = get_article(api_base_url, org_name_short, learner_headers, board_article_id)
    assert article["title"] == original["title"]
