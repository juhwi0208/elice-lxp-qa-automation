"""학습과목 TC 명세의 기존 `/org/{org}` API 클라이언트."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

from part1_api_automation.utils import api_client


_ORG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class LegacyCourseApi:
    """과목·퀴즈·트랙의 기존 통합 API 경로를 캡슐화한다."""

    base_url: str
    org_name_short: str

    def __post_init__(self) -> None:
        if not _ORG_PATTERN.fullmatch(self.org_name_short):
            raise ValueError("기관 식별자는 URL 경로에 사용할 수 있는 형식이어야 합니다.")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/org/{self.org_name_short}/{path.strip('/')}/"

    def list_courses(
        self,
        headers: dict,
        *,
        offset: int | None = 0,
        count: int | None = 20,
    ) -> requests.Response:
        params = {
            key: value
            for key, value in {"offset": offset, "count": count}.items()
            if value is not None
        }
        return api_client.get(
            self._url("course/list"),
            headers=headers,
            params=params,
        )

    def get_course(self, course_id: int, headers: dict) -> requests.Response:
        return api_client.get(
            self._url("course/get"),
            headers=headers,
            params={"course_id": course_id},
        )

    def list_lectures(
        self,
        course_id: int,
        headers: dict,
        *,
        offset: int = 0,
        count: int = 20,
    ) -> requests.Response:
        return api_client.get(
            self._url("lecture/list"),
            headers=headers,
            params={
                "course_id": course_id,
                "offset": offset,
                "count": count,
            },
        )

    def get_lecture(self, lecture_id: int, headers: dict) -> requests.Response:
        return api_client.get(
            self._url("lecture/get"),
            headers=headers,
            params={"lecture_id": lecture_id},
        )

    def list_lecture_pages(
        self,
        lecture_id: int,
        locator_type: int,
        headers: dict,
        *,
        offset: int = 0,
        count: int = 20,
    ) -> requests.Response:
        return api_client.get(
            self._url("lecture_page/list"),
            headers=headers,
            params={
                "lecture_id": lecture_id,
                "locator_type": locator_type,
                "offset": offset,
                "count": count,
            },
        )

    def get_lecture_page(
        self,
        lecture_page_id: int,
        headers: dict,
    ) -> requests.Response:
        return api_client.get(
            self._url("lecture_page/get"),
            headers=headers,
            params={"lecture_page_id": lecture_page_id},
        )

    def get_material_quiz(
        self,
        material_quiz_id: int,
        headers: dict,
        *,
        user_id: int | None = None,
    ) -> requests.Response:
        params = {"material_quiz_id": material_quiz_id}
        if user_id is not None:
            params["user_id"] = user_id
        return api_client.get(
            self._url("material_quiz/get"),
            headers=headers,
            params=params,
        )

    def list_material_quiz_responses(
        self,
        material_quiz_id: int,
        user_id: int | None,
        headers: dict,
        *,
        offset: int = 0,
        count: int = 20,
        contain_only_last: bool = False,
        include_answer: bool = False,
    ) -> requests.Response:
        params = {
            "material_quiz_id": material_quiz_id,
            "offset": offset,
            "count": count,
            "is_contain_only_last": str(contain_only_last).lower(),
            "is_include_answer": str(include_answer).lower(),
        }
        if user_id is not None:
            params["user_id"] = user_id

        return api_client.get(
            self._url("material_quiz/response/list"),
            headers=headers,
            params=params,
        )

    def list_test_admissions(
        self,
        user_id: int,
        lecture_id: int,
        headers: dict,
        *,
        offset: int = 0,
        count: int = 20,
    ) -> requests.Response:
        return api_client.get(
            self._url("user/test_admission/list"),
            headers=headers,
            params={
                "user_id": user_id,
                "lecture_id": lecture_id,
                "offset": offset,
                "count": count,
            },
        )

    def list_course_completion_statuses(
        self,
        course_id: int,
        user_id: int,
        headers: dict,
        *,
        offset: int = 0,
        count: int = 20,
    ) -> requests.Response:
        return api_client.get(
            self._url("course/completion/status/list"),
            headers=headers,
            params={
                "course_id": course_id,
                "user_id": user_id,
                "offset": offset,
                "count": count,
            },
        )

    def get_track(self, track_id: int | None, headers: dict) -> requests.Response:
        params = {} if track_id is None else {"track_id": track_id}
        return api_client.get(
            self._url("track/get"),
            headers=headers,
            params=params,
        )

    def add_track_course(
        self,
        track_id: int,
        course_id: int | None,
        headers: dict,
        *,
        confirmed: bool = False,
    ) -> requests.Response:
        data = {"track_id": track_id}
        if course_id is not None:
            data["course_id"] = course_id
        return api_client.post(
            self._url("track/course/add"),
            headers=headers,
            data=data,
            confirmed=confirmed,
        )

    def remove_track_course(
        self,
        track_id: int,
        course_id: int,
        headers: dict,
        *,
        confirmed: bool = False,
    ) -> requests.Response:
        return api_client.post(
            self._url("track/course/delete"),
            headers=headers,
            data={"track_id": track_id, "course_id": course_id},
            confirmed=confirmed,
        )

    def move_track_course(
        self,
        track_id: int,
        order_no: int,
        new_order_no: int,
        headers: dict,
        *,
        confirmed: bool = False,
    ) -> requests.Response:
        return api_client.post(
            self._url("track/course/move"),
            headers=headers,
            data={
                "track_id": track_id,
                "order_no": order_no,
                "new_order_no": new_order_no,
            },
            confirmed=confirmed,
        )

    def edit_course(
        self,
        course_id: int,
        fields: dict,
        headers: dict,
        *,
        confirmed: bool = False,
    ) -> requests.Response:
        serialized_fields = {
            key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if isinstance(value, (dict, list))
            else value
            for key, value in fields.items()
        }
        return api_client.post(
            self._url("course/edit"),
            headers=headers,
            data={"course_id": course_id, **serialized_fields},
            confirmed=confirmed,
        )

    def edit_lecture(
        self,
        lecture_id: int,
        fields: dict,
        headers: dict,
        *,
        confirmed: bool = False,
    ) -> requests.Response:
        return api_client.post(
            self._url("lecture/edit"),
            headers=headers,
            data={"lecture_id": lecture_id, **fields},
            confirmed=confirmed,
        )

    def edit_lecture_page_visibility(
        self,
        lecture_page_id: int,
        *,
        is_for_stats: bool,
        is_opened: bool,
        headers: dict,
        confirmed: bool = False,
    ) -> requests.Response:
        return api_client.post(
            self._url("lecture_page/visibility/edit"),
            headers=headers,
            data={
                "lecture_page_id": lecture_page_id,
                "is_for_stats": is_for_stats,
                "is_opened": is_opened,
            },
            confirmed=confirmed,
        )

    def add_material_quiz_response(
        self,
        material_quiz_id: int,
        resource_id: int | None,
        answer: str,
        headers: dict,
        *,
        confirmed: bool = False,
    ) -> requests.Response:
        data: dict[str, object] = {
            "material_quiz_id": material_quiz_id,
            "answer": answer,
        }
        if resource_id is not None:
            data["resource_id"] = resource_id

        return api_client.post(
            self._url("material_quiz/response/add"),
            headers=headers,
            data=data,
            confirmed=confirmed,
        )

    def get_material_quiz_response(
        self,
        quiz_response_id: int,
        headers: dict,
    ) -> requests.Response:
        return api_client.get(
            self._url("material_quiz/response/get"),
            headers=headers,
            params={"quiz_response_id": quiz_response_id},
        )

    def reset_material_quiz_response(
        self,
        material_quiz_id: int,
        headers: dict,
        *,
        user_id: int | None = None,
        confirmed: bool = False,
    ) -> requests.Response:
        """HeadTA 권한으로 지정 학습자의 퀴즈 응답을 초기화한다."""
        params = {"material_quiz_id": material_quiz_id}
        if user_id is not None:
            params["user_id"] = user_id
        return api_client.get_state_changing(
            self._url("material_quiz/response/reset"),
            headers=headers,
            params=params,
            confirmed=confirmed,
        )

    def reset_test_by_self(
        self,
        lecture_id: int,
        headers: dict,
        *,
        confirmed: bool = False,
    ) -> requests.Response:
        return api_client.post(
            self._url("lecture/test/reset/by_self"),
            headers=headers,
            data={"lecture_id": lecture_id},
            confirmed=confirmed,
        )
