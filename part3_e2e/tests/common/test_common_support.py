"""강의실 설정과 공통 URL 생성기의 단위 테스트."""

import pytest

from part3_e2e.config import (
    E2EConfigurationError,
    E2ESettings,
    load_classroom_context,
    load_course_test_data,
)
from part3_e2e.pages.common.base_page import build_web_url


def test_classroom_context_accepts_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    classroom_id = "28f79a10-c14b-4531-9feb-53d9a5c157fc"
    monkeypatch.setenv("LXP_CLASSROOM_ID", classroom_id)

    assert load_classroom_context().classroom_id == classroom_id


def test_classroom_context_rejects_non_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LXP_CLASSROOM_ID", "wrong-classroom")

    with pytest.raises(E2EConfigurationError):
        load_classroom_context()


def test_build_web_url_keeps_path_inside_qa_host() -> None:
    settings = E2ESettings(
        accounts_base_url="https://dev-qatrack-accounts.dev.elicer.io",
        web_base_url="https://dev-qatrack-web.dev.elicer.io",
        org_name_short="academy",
    )

    assert build_web_url(settings, "/classrooms/example/courses") == (
        "https://dev-qatrack-web.dev.elicer.io/classrooms/example/courses"
    )


def test_course_test_data_uses_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LXP_COURSE_NAME", raising=False)
    monkeypatch.delenv("LXP_TEST_LECTURE_NAME", raising=False)
    monkeypatch.delenv("LXP_TEST_ANSWER", raising=False)

    data = load_course_test_data()

    assert data.course_name == "SANDBOX"
    assert data.test_lecture_name == "TEST"
    assert data.test_answer == ""
