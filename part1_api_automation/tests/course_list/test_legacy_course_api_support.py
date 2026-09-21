"""기존 학습과목 통합 API 경로와 요청 데이터 단위 테스트."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from part1_api_automation.utils import api_client
from part1_api_automation.utils.config import Config
from part1_api_automation.utils.legacy_course_api import LegacyCourseApi


class FakeResponse:
    status_code = 200
    text = "ok"


@pytest.fixture(autouse=True)
def isolated_http(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LXP_API_BASE_URL", "https://dev-qatrack-api.dev.elicer.io")
    monkeypatch.setattr(Config, "CALL_INTERVAL", 0)
    api_client.reset_safety_state()
    yield
    api_client.reset_safety_state()


def test_legacy_read_paths_and_params(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)
    client = LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "academy")

    client.list_courses({}, offset=5, count=10)
    client.get_course(727, {})
    client.list_lectures(727, {}, offset=1, count=15)
    client.get_lecture(1581, {})
    client.list_lecture_pages(1581, 0, {}, offset=2, count=5)
    client.get_lecture_page(3001, {})
    client.get_material_quiz(1581, {}, user_id=100)
    client.get_track(28, {})

    assert [(call["method"], call["url"], call["params"]) for call in calls] == [
        (
            "GET",
            "https://dev-qatrack-api.dev.elicer.io/org/academy/course/list/",
            {"offset": 5, "count": 10},
        ),
        (
            "GET",
            "https://dev-qatrack-api.dev.elicer.io/org/academy/course/get/",
            {"course_id": 727},
        ),
        (
            "GET",
            "https://dev-qatrack-api.dev.elicer.io/org/academy/lecture/list/",
            {"course_id": 727, "offset": 1, "count": 15},
        ),
        (
            "GET",
            "https://dev-qatrack-api.dev.elicer.io/org/academy/lecture/get/",
            {"lecture_id": 1581},
        ),
        (
            "GET",
            "https://dev-qatrack-api.dev.elicer.io/org/academy/lecture_page/list/",
            {"lecture_id": 1581, "locator_type": 0, "offset": 2, "count": 5},
        ),
        (
            "GET",
            "https://dev-qatrack-api.dev.elicer.io/org/academy/lecture_page/get/",
            {"lecture_page_id": 3001},
        ),
        (
            "GET",
            "https://dev-qatrack-api.dev.elicer.io/org/academy/material_quiz/get/",
            {"material_quiz_id": 1581, "user_id": 100},
        ),
        (
            "GET",
            "https://dev-qatrack-api.dev.elicer.io/org/academy/track/get/",
            {"track_id": 28},
        ),
    ]


def test_track_course_add_keeps_mutation_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LXP_ALLOW_MUTATING_REQUESTS", raising=False)
    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: FakeResponse())
    client = LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "academy")

    with pytest.raises(api_client.UnsafeRequestError):
        client.add_track_course(28, 727, {}, confirmed=True)


def test_required_query_params_can_be_omitted_for_boundary_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)
    client = LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "academy")

    client.get_track(None, {})
    client.list_courses({}, offset=None, count=20)
    client.list_courses({}, offset=0, count=None)

    assert [call["params"] for call in calls] == [
        {},
        {"count": 20},
        {"offset": 0},
    ]


def test_learning_state_read_paths_and_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)
    client = LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "academy")

    client.list_material_quiz_responses(11, 22, {}, offset=3, count=4)
    client.list_test_admissions(22, 33, {}, offset=5, count=6)
    client.list_course_completion_statuses(44, 22, {}, offset=7, count=8)
    client.get_material_quiz_response(55, {})

    assert [(call["url"], call["params"]) for call in calls] == [
        (
            "https://dev-qatrack-api.dev.elicer.io/org/academy/material_quiz/response/list/",
            {
                "material_quiz_id": 11,
                "user_id": 22,
                "offset": 3,
                "count": 4,
                "is_contain_only_last": "false",
                "is_include_answer": "false",
            },
        ),
        (
            "https://dev-qatrack-api.dev.elicer.io/org/academy/user/test_admission/list/",
            {"user_id": 22, "lecture_id": 33, "offset": 5, "count": 6},
        ),
        (
            "https://dev-qatrack-api.dev.elicer.io/org/academy/course/completion/status/list/",
            {"course_id": 44, "user_id": 22, "offset": 7, "count": 8},
        ),
        (
            "https://dev-qatrack-api.dev.elicer.io/org/academy/material_quiz/response/get/",
            {"quiz_response_id": 55},
        ),
    ]


def test_material_quiz_response_list_omits_user_id_for_self_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(requests, "request", fake_request)
    client = LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "academy")

    client.list_material_quiz_responses(11, None, {}, offset=0, count=20)

    assert "user_id" not in calls[0]["params"]
    assert calls[0]["params"]["material_quiz_id"] == 11


def test_mutation_paths_and_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setenv("LXP_ALLOW_MUTATING_REQUESTS", "true")
    monkeypatch.setattr(requests, "request", fake_request)
    client = LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "academy")

    client.add_track_course(1, 2, {}, confirmed=True)
    client.remove_track_course(1, 2, {}, confirmed=True)
    client.move_track_course(1, 0, 1, {}, confirmed=True)
    client.edit_course(2, {"title": "course"}, {}, confirmed=True)
    client.edit_lecture(3, {"title": "lecture"}, {}, confirmed=True)
    client.edit_lecture_page_visibility(
        4,
        is_for_stats=True,
        is_opened=False,
        headers={},
        confirmed=True,
    )
    client.add_material_quiz_response(5, 6, "answer", {}, confirmed=True)
    client.reset_material_quiz_response(5, {}, user_id=7, confirmed=True)
    client.reset_test_by_self(3, {}, confirmed=True)

    assert [(call["url"], call["data"]) for call in calls] == [
        ("https://dev-qatrack-api.dev.elicer.io/org/academy/track/course/add/", {"track_id": 1, "course_id": 2}),
        ("https://dev-qatrack-api.dev.elicer.io/org/academy/track/course/delete/", {"track_id": 1, "course_id": 2}),
        ("https://dev-qatrack-api.dev.elicer.io/org/academy/track/course/move/", {"track_id": 1, "order_no": 0, "new_order_no": 1}),
        ("https://dev-qatrack-api.dev.elicer.io/org/academy/course/edit/", {"course_id": 2, "title": "course"}),
        ("https://dev-qatrack-api.dev.elicer.io/org/academy/lecture/edit/", {"lecture_id": 3, "title": "lecture"}),
        (
            "https://dev-qatrack-api.dev.elicer.io/org/academy/lecture_page/visibility/edit/",
            {"lecture_page_id": 4, "is_for_stats": True, "is_opened": False},
        ),
        (
            "https://dev-qatrack-api.dev.elicer.io/org/academy/material_quiz/response/add/",
            {"material_quiz_id": 5, "resource_id": 6, "answer": "answer"},
        ),
        (
            "https://dev-qatrack-api.dev.elicer.io/org/academy/material_quiz/response/reset/",
            None,
        ),
        ("https://dev-qatrack-api.dev.elicer.io/org/academy/lecture/test/reset/by_self/", {"lecture_id": 3}),
    ]
    assert calls[-2]["method"] == "GET"
    assert calls[-2]["params"] == {"material_quiz_id": 5, "user_id": 7}


def test_quiz_response_add_omits_missing_resource_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setenv("LXP_ALLOW_MUTATING_REQUESTS", "true")
    monkeypatch.setattr(requests, "request", fake_request)
    client = LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "academy")

    client.add_material_quiz_response(5, None, "[0]", {}, confirmed=True)

    assert calls[0]["data"] == {
        "material_quiz_id": 5,
        "answer": "[0]",
    }


def test_course_edit_serializes_nested_form_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setenv("LXP_ALLOW_MUTATING_REQUESTS", "true")
    monkeypatch.setattr(requests, "request", fake_request)
    client = LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "academy")

    client.edit_course(
        2,
        {
            "title": "course",
            "target_audience": ["learner"],
            "completion_info": {"enabled": False},
        },
        {},
        confirmed=True,
    )

    assert calls[0]["data"] == {
        "course_id": 2,
        "title": "course",
        "target_audience": '["learner"]',
        "completion_info": '{"enabled":false}',
    }


def test_org_path_rejects_unsafe_value() -> None:
    with pytest.raises(ValueError):
        LegacyCourseApi("https://dev-qatrack-api.dev.elicer.io", "../another-org")
