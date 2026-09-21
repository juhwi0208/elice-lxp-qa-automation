"""Part 1 API 자동화 전용 pytest fixture와 안전 중단 hook."""

import os

import pytest
from dotenv import load_dotenv

from part1_api_automation.utils.api_client import AbortTestError
from part1_api_automation.utils.config import require_base_url, require_service_base_url
from part1_api_automation.utils.token_manager import (
    educator_auth_header,
    learner_auth_header,
    other_learner_auth_header,
)

load_dotenv()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """cleanup 경로가 없는 게시판 변경 테스트를 API 호출 전에 차단한다."""
    cleanup_path = os.getenv("LXP_BOARD_ARTICLE_DELETE_PATH", "").strip()
    if cleanup_path:
        return

    for item in items:
        path = getattr(item, "path", None)
        if (
            path is not None
            and "board" in path.parts
            and item.get_closest_marker("mutating") is not None
        ):
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "게시글 cleanup 경로가 없어 생성 테스트를 차단합니다: "
                        "LXP_BOARD_ARTICLE_DELETE_PATH"
                    )
                )
            )


def pytest_exception_interact(node, call, report):
    """처리되지 않은 5xx 중단 예외가 발생하면 API 테스트 실행을 종료한다."""
    if call.excinfo and call.excinfo.errisinstance(AbortTestError):
        error = call.excinfo.value
        classification = (
            f"HTTP {error.status_code} ({error.error_code})"
            if error.status_code is not None
            else "이전 5xx 응답"
        )
        pytest.exit(
            f"{classification} 서버 오류가 감지되어 "
            "추가 API 호출을 막고 테스트를 중단합니다.",
            returncode=1,
        )


def _require_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"필수 환경변수 '{key}'가 설정되지 않았습니다. .env.example을 참고하세요."
        )
    return value


@pytest.fixture(scope="session")
def qa_environment_name() -> str:
    return "qa"


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return require_base_url()


@pytest.fixture(scope="session")
def classroom_api_base_url() -> str:
    return require_service_base_url("classroom")


@pytest.fixture(scope="session")
def course_api_base_url() -> str:
    return require_service_base_url("course")


@pytest.fixture(scope="session")
def dashboard_api_base_url() -> str:
    return require_service_base_url("dashboard")


@pytest.fixture(scope="session")
def org_name_short() -> str:
    return _require_env("LXP_ORG_NAME_SHORT")


@pytest.fixture(scope="session")
def classroom_id() -> str:
    return _require_env("LXP_CLASSROOM_ID")


@pytest.fixture(scope="session")
def learner_headers(org_name_short: str) -> dict:
    headers = learner_auth_header()
    headers["x-elice-org-name-short"] = org_name_short
    return headers


@pytest.fixture(scope="session")
def educator_headers(org_name_short: str) -> dict:
    headers = educator_auth_header()
    headers["x-elice-org-name-short"] = org_name_short
    return headers


@pytest.fixture(scope="session")
def other_learner_headers(org_name_short: str) -> dict:
    headers = other_learner_auth_header()
    headers["x-elice-org-name-short"] = org_name_short
    return headers


@pytest.fixture(scope="session")
def course_id() -> int:
    """연결 과목 테스트에 사용하는 QA 과목 ID를 반환한다."""
    return int(_require_env("LXP_COURSE_ID"))
