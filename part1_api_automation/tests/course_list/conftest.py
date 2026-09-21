"""학습과목 API 테스트 전용 fixture."""

from __future__ import annotations

import os

import pytest

from part1_api_automation.utils.course_api import CourseApi
from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import assert_http_status


@pytest.fixture(scope="session")
def course_name() -> str:
    return os.getenv("LXP_COURSE_NAME", "SANDBOX").strip() or "SANDBOX"


@pytest.fixture(scope="session")
def test_lecture_name() -> str:
    return os.getenv("LXP_TEST_LECTURE_NAME", "TEST").strip() or "TEST"


def _positive_int_or_skip(name: str) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"학습과목 API 환경변수 미설정: {name}")
    try:
        parsed = int(value)
    except ValueError:
        pytest.fail(f"{name}은 양의 정수여야 합니다.")
    if parsed <= 0:
        pytest.fail(f"{name}은 양의 정수여야 합니다.")
    return parsed


@pytest.fixture(scope="session")
def private_course_id() -> int:
    return _positive_int_or_skip("LXP_PRIVATE_COURSE_ID")


@pytest.fixture(scope="session")
def course_id() -> int:
    return _positive_int_or_skip("LXP_COURSE_ID")


@pytest.fixture(scope="session")
def material_quiz_id() -> int:
    return _positive_int_or_skip("LXP_MATERIAL_QUIZ_ID")


@pytest.fixture(scope="session")
def lecture_id() -> int:
    return _positive_int_or_skip("LXP_LECTURE_ID")


@pytest.fixture(scope="session")
def lecture_page_id() -> int:
    return _positive_int_or_skip("LXP_LECTURE_PAGE_ID")


@pytest.fixture(scope="session")
def lecture_locator_type() -> int:
    value = os.getenv("LXP_LECTURE_LOCATOR_TYPE", "0").strip()
    try:
        locator_type = int(value)
    except ValueError:
        pytest.fail("LXP_LECTURE_LOCATOR_TYPE은 0(Main) 또는 1(Sub)이어야 합니다.")
    if locator_type not in (0, 1):
        pytest.fail("LXP_LECTURE_LOCATOR_TYPE은 0(Main) 또는 1(Sub)이어야 합니다.")
    return locator_type


@pytest.fixture(scope="session")
def track_id() -> int:
    return _positive_int_or_skip("LXP_TRACK_ID")


@pytest.fixture(scope="session")
def boundary_course_id() -> int:
    return _positive_int_or_skip("LXP_BOUNDARY_COURSE_ID")


@pytest.fixture(scope="session")
def learner_user_id() -> int:
    return _positive_int_or_skip("LXP_LEARNER_USER_ID")


@pytest.fixture(scope="session")
def quiz_resource_id() -> int | None:
    """퀴즈 유형에 따라 선택적으로 사용하는 resource_id를 반환한다.

    현재 QA 객관식 퀴즈 응답은 ``resource_id=null``로 저장되므로 값이 없으면
    요청에서도 해당 필드를 생략한다. 실제 API 응답에 양의 정수가 확인된
    퀴즈에서만 환경변수를 설정한다.
    """
    value = os.getenv("LXP_QUIZ_RESOURCE_ID", "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        pytest.fail("LXP_QUIZ_RESOURCE_ID는 양의 정수여야 합니다.")
    if parsed <= 0:
        pytest.fail("LXP_QUIZ_RESOURCE_ID는 양의 정수여야 합니다.")
    return parsed


@pytest.fixture(scope="session")
def allow_course_mutations() -> None:
    enabled = os.getenv("LXP_ALLOW_MUTATING_REQUESTS", "false").strip().lower()
    if enabled != "true":
        pytest.skip(
            "학습과목 변경 API가 비활성화되어 있습니다: "
            "LXP_ALLOW_MUTATING_REQUESTS=true"
        )


@pytest.fixture(scope="session")
def learner_course_api(
    classroom_api_base_url: str,
    course_api_base_url: str,
    learner_headers: dict,
) -> CourseApi:
    return CourseApi(classroom_api_base_url, course_api_base_url, learner_headers)


@pytest.fixture(scope="session")
def legacy_course_api(
    api_base_url: str,
    org_name_short: str,
) -> LegacyCourseApi:
    return LegacyCourseApi(api_base_url, org_name_short)


@pytest.fixture
def classroom_courses(
    learner_course_api: CourseApi,
    classroom_id: str,
) -> list[dict]:
    """각 테스트 시작 시 최신 강의실 과목 목록을 조회한다.

    변경 테스트의 실행 순서에 따라 세션 캐시가 오래된 목록을 반환하지 않도록
    function scope를 사용한다.
    """
    response = learner_course_api.list_classroom_courses(classroom_id)
    assert_http_status(response, 200)
    body = response.json()
    assert isinstance(body, list), "강의실 학습과목 목록 응답은 배열이어야 합니다."
    return body


@pytest.fixture
def sandbox_course(classroom_courses: list[dict], course_name: str) -> dict:
    matches = [course for course in classroom_courses if course.get("title") == course_name]
    assert len(matches) == 1, (
        f"{course_name!r} 과목은 QA 강의실 목록에 정확히 한 번 존재해야 합니다. "
        f"실제 개수: {len(matches)}"
    )
    return matches[0]
