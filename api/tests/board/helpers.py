"""게시판 API 테스트 공통 helper."""

from __future__ import annotations

from collections.abc import Callable
from typing import BinaryIO
from uuid import uuid4

from part1_api_automation.utils import api_client
from part1_api_automation.utils.security import mask_sensitive_data


FILE_SIZE_LIMIT = 31_457_280  # 30MB


def article_edit_url(api_base_url: str, org_name_short: str) -> str:
    """게시글 생성/수정 API URL을 반환한다."""
    return f"{api_base_url}/org/{org_name_short}/board/article/edit/"


def article_get_url(api_base_url: str, org_name_short: str) -> str:
    """게시글 상세 조회 API URL을 반환한다."""
    return f"{api_base_url}/org/{org_name_short}/board/article/get/"


def unique_title(prefix: str) -> str:
    """QA 자동화로 생성한 게시글을 쉽게 구분할 수 있는 제목을 만든다."""
    return f"[QA-AUTO] {prefix}-{uuid4().hex[:8]}"


def valid_content(text: str = "게시판 API 자동화 테스트") -> str:
    """실제 Web Editor가 전송하는 HTML 형식과 유사한 content를 만든다."""
    return (
        '<p class="editor-paragraph" dir="ltr">'
        f'<span style="white-space: pre-wrap;">{text}</span>'
        "</p>"
    )


def multipart(
    fields: dict,
    attachments: list[tuple[str, BinaryIO, str]] | None = None,
):
    """일반 필드와 첨부파일을 requests용 multipart/form-data 형태로 변환한다."""
    parts = []

    for key, value in fields.items():
        parts.append(
            (
                key,
                (
                    None,
                    str(value).lower() if isinstance(value, bool) else str(value),
                ),
            )
        )

    if attachments:
        for filename, file_obj, content_type in attachments:
            parts.append(
                (
                    "attachment_files",
                    (
                        filename,
                        file_obj,
                        content_type,
                    ),
                )
            )

    return parts


def default_payload(classroom_id: str) -> dict:
    """게시글 생성 테스트에서 사용할 기본 payload를 반환한다."""
    return {
        "title": unique_title("board-create"),
        "content": valid_content(),
        "is_secret": "false",
        "classroom_id": classroom_id,
    }


def _register_created_article_if_present(
    body: dict,
    register_created_board_article: Callable[[int], None] | None,
) -> int | None:
    """
    응답에 board_article_id가 있으면 cleanup 대상으로 등록한다.

    이후 assertion이 실패하더라도 이미 생성된 게시글이 테스트 데이터로
    남지 않도록 응답 확인 직후 등록한다.
    """
    board_article_id = body.get("board_article_id")

    if isinstance(board_article_id, int) and register_created_board_article is not None:
        register_created_board_article(board_article_id)

    return board_article_id if isinstance(board_article_id, int) else None


def assert_success(
    response,
    register_created_board_article: Callable[[int], None] | None = None,
) -> dict:
    """
    게시글 생성 API의 성공 응답을 검증한다.

    게시글이 생성된 경우 board_article_id를 cleanup registry에 등록하여
    테스트 종료 후 자동 삭제할 수 있도록 한다.
    """
    assert response.status_code == 200, (
        f"HTTP 200이 아닙니다: status={response.status_code}, "
        f"body={mask_sensitive_data(response.text)[:500]}"
    )

    body = response.json()

    board_article_id = _register_created_article_if_present(
        body,
        register_created_board_article,
    )

    result = body.get("_result", {})

    assert result.get("status") == "ok", mask_sensitive_data(body)
    assert result.get("status_code") == 200, mask_sensitive_data(body)
    assert result.get("reason") is None, mask_sensitive_data(body)
    assert isinstance(board_article_id, int), mask_sensitive_data(body)

    return body


def assert_rejected(
    response,
    register_created_board_article: Callable[[int], None] | None = None,
) -> None:
    """
    게시글 생성 요청이 거부되었는지 검증한다.

    실패해야 하는 요청이 서버 문제로 게시글을 생성한 경우에도
    board_article_id를 cleanup registry에 등록하여 테스트 데이터를 정리한다.
    """
    if response.status_code != 200:
        assert 400 <= response.status_code < 500, (
            f"예상하지 못한 HTTP 상태: status={response.status_code}, "
            f"body={mask_sensitive_data(response.text)[:500]}"
        )
        return

    body = response.json()

    _register_created_article_if_present(
        body,
        register_created_board_article,
    )

    result = body.get("_result", {})

    assert result.get("status") != "ok", (
        f"실패해야 하는 요청이 성공했습니다: {mask_sensitive_data(body)}"
    )

    assert "board_article_id" not in body, (
        f"실패 응답에 board_article_id가 포함됐습니다: {mask_sensitive_data(body)}"
    )


def get_article(
    api_base_url: str,
    org_name_short: str,
    learner_headers: dict,
    board_article_id: int,
) -> dict:
    """board_article_id로 게시글 상세를 조회한다."""
    response = api_client.get(
        article_get_url(api_base_url, org_name_short),
        headers=learner_headers,
        params={"board_article_id": board_article_id},
    )

    assert response.status_code == 200, (
        f"게시글 조회 HTTP 상태가 200이 아닙니다: "
        f"status={response.status_code}, "
        f"body={mask_sensitive_data(response.text)[:500]}"
    )

    body = response.json()
    result = body.get("_result", {})

    assert result.get("status") == "ok", mask_sensitive_data(body)
    assert result.get("status_code") == 200, mask_sensitive_data(body)
    assert "board_article" in body, mask_sensitive_data(body)

    return body["board_article"]


def article_list_url(api_base_url: str, org_name_short: str) -> str:
    """게시글 목록 조회 API URL을 반환한다."""
    return f"{api_base_url}/org/{org_name_short}/board/article/list/"


def board_list_url(api_base_url: str, org_name_short: str) -> str:
    """게시판 목록 조회 API URL을 반환한다."""
    return f"{api_base_url}/org/{org_name_short}/board/list/"


def create_article(
    api_base_url: str,
    org_name_short: str,
    headers: dict,
    payload: dict,
    register_created_board_article: Callable[[int], None],
    attachments: list[tuple[str, BinaryIO, str]] | None = None,
) -> int:
    """테스트용 게시글을 생성하고 ID를 반환한다."""
    response = api_client.post(
        article_edit_url(api_base_url, org_name_short),
        headers=headers,
        files=multipart(
            payload,
            attachments=attachments,
        ),
        confirmed=True,
    )

    body = assert_success(
        response,
        register_created_board_article,
    )

    return body["board_article_id"]


def get_board_article_list(
    api_base_url: str,
    org_name_short: str,
    headers: dict,
    board_id: int,
    *,
    offset: int = 0,
    count: int = 20,
) -> dict:
    """특정 게시판의 게시글 목록을 조회한다."""
    response = api_client.get(
        article_list_url(api_base_url, org_name_short),
        headers=headers,
        params={
            "board_id": board_id,
            "offset": offset,
            "count": count,
        },
    )

    assert response.status_code == 200, (
        f"게시글 목록 조회 HTTP 상태가 200이 아닙니다: "
        f"status={response.status_code}, "
        f"body={mask_sensitive_data(response.text)[:500]}"
    )

    body = response.json()
    result = body.get("_result", {})

    assert result.get("status") == "ok", mask_sensitive_data(body)
    assert result.get("status_code") == 200, mask_sensitive_data(body)
    assert isinstance(body.get("board_article_count"), int), mask_sensitive_data(body)
    assert isinstance(body.get("board_articles"), list), mask_sensitive_data(body)

    return body


def get_postable_board_id(
    api_base_url: str,
    org_name_short: str,
    headers: dict,
    course_id: int,
) -> int:
    """QA 과목에서 조회·작성 가능한 게시판 ID 하나를 반환한다."""
    response = api_client.get(
        board_list_url(api_base_url, org_name_short),
        headers=headers,
        params={
            "course_id": course_id,
            "offset": 0,
            "count": 20,
        },
    )

    assert response.status_code == 200, (
        f"게시판 목록 조회 HTTP 상태가 200이 아닙니다: "
        f"status={response.status_code}, "
        f"body={mask_sensitive_data(response.text)[:500]}"
    )

    body = response.json()
    result = body.get("_result", {})

    assert result.get("status") == "ok", mask_sensitive_data(body)

    boards = body.get("boards", [])

    for board in boards:
        if board.get("is_viewable") and board.get("is_postable"):
            board_id = board.get("id")

            if isinstance(board_id, int):
                return board_id

    raise AssertionError(
        "QA 과목에서 학습자가 조회하고 작성할 수 있는 게시판을 찾지 못했습니다."
    )


def assert_article_detail_rejected(
    response,
    *,
    expected_fail_code: str | None = None,
) -> dict | None:
    """게시글 상세 조회가 인증/권한/검증 오류로 거부되었는지 확인한다."""
    if response.status_code != 200:
        assert 400 <= response.status_code < 500, (
            f"예상하지 못한 HTTP 상태입니다: "
            f"status={response.status_code}, "
            f"body={mask_sensitive_data(response.text)[:500]}"
        )

        try:
            return response.json()
        except ValueError:
            return None

    body = response.json()
    result = body.get("_result", {})

    assert result.get("status") == "fail", mask_sensitive_data(body)
    assert "board_article" not in body, mask_sensitive_data(body)

    if expected_fail_code is not None:
        assert body.get("fail_code") == expected_fail_code, (
            f"기대한 fail_code={expected_fail_code}, "
            f"실제={body.get('fail_code')}, "
            f"body={mask_sensitive_data(body)}"
        )

    return body
