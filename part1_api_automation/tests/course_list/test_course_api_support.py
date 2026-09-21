"""네트워크를 호출하지 않는 학습과목 API 경로 단위 테스트."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from part1_api_automation.utils import course_api
from part1_api_automation.utils.course_api import CourseApi


@dataclass
class FakeResponse:
    status_code: int = 200


@pytest.fixture
def client() -> CourseApi:
    return CourseApi(
        classroom_base_url="https://dev-qatrack-classroom-api.dev.elicer.io",
        course_base_url="https://dev-qatrack-course-api.dev.elicer.io",
        headers={"Authorization": "Bearer redacted"},
    )


def test_classroom_course_paths(
    monkeypatch: pytest.MonkeyPatch,
    client: CourseApi,
) -> None:
    calls = []
    monkeypatch.setattr(
        course_api.api_client,
        "get",
        lambda url, headers, params=None: calls.append((url, params)) or FakeResponse(),
    )

    client.list_classroom_courses("classroom-id")
    client.get_classroom_course("classroom-id", 727)

    assert calls == [
        (
            "https://dev-qatrack-classroom-api.dev.elicer.io/"
            "classroom/classroom-id/course",
            {"count": 20, "skip": 0},
        ),
        (
            "https://dev-qatrack-classroom-api.dev.elicer.io/"
            "classroom/classroom-id/course/727",
            None,
        ),
    ]


def test_opened_lecture_query_uses_ui_depth_filter(
    monkeypatch: pytest.MonkeyPatch,
    client: CourseApi,
) -> None:
    captured = {}

    def fake_get(url, headers, params=None):
        captured.update(url=url, params=params)
        return FakeResponse()

    monkeypatch.setattr(course_api.api_client, "get", fake_get)

    client.list_opened_lectures(727)

    assert captured == {
        "url": "https://dev-qatrack-course-api.dev.elicer.io/lecture",
        "params": {
            "elice_course_id": 727,
            "filter_is_opened": "true",
            "filter_depth": 1,
            "count": 40,
            "skip": 0,
        },
    }
