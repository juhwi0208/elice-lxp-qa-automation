"""학습과목 조회 API 호출을 캡슐화한 공통 클라이언트."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from part1_api_automation.utils import api_client


@dataclass(frozen=True)
class CourseApi:
    classroom_base_url: str
    course_base_url: str
    headers: dict

    def list_classroom_courses(
        self,
        classroom_id: str,
        *,
        count: int = 20,
        skip: int = 0,
    ) -> requests.Response:
        return api_client.get(
            f"{self.classroom_base_url}/classroom/{classroom_id}/course",
            headers=self.headers,
            params={"count": count, "skip": skip},
        )

    def get_classroom_course(
        self,
        classroom_id: str,
        course_id: int,
    ) -> requests.Response:
        return api_client.get(
            f"{self.classroom_base_url}/classroom/{classroom_id}/course/{course_id}",
            headers=self.headers,
        )

    def get_course(self, course_id: int) -> requests.Response:
        return api_client.get(
            f"{self.course_base_url}/course/{course_id}",
            headers=self.headers,
            params={"elice_course_id": course_id},
        )

    def get_curriculum(self, course_id: int) -> requests.Response:
        return api_client.get(
            f"{self.course_base_url}/course/{course_id}/curriculum",
            headers=self.headers,
            params={"elice_course_id": course_id},
        )

    def get_course_stats(self, course_id: int) -> requests.Response:
        return api_client.get(
            f"{self.course_base_url}/course/{course_id}/stats",
            headers=self.headers,
            params={"elice_course_id": course_id},
        )

    def list_opened_lectures(
        self,
        course_id: int,
        *,
        count: int = 40,
        skip: int = 0,
    ) -> requests.Response:
        return api_client.get(
            f"{self.course_base_url}/lecture",
            headers=self.headers,
            params={
                "elice_course_id": course_id,
                "filter_is_opened": "true",
                "filter_depth": 1,
                "count": count,
                "skip": skip,
            },
        )
