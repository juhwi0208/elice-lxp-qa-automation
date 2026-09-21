"""Part 3 E2E 전체에 공통 fixture와 수집 규칙을 등록한다."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv



from part3_e2e.fixtures.tc_result_collector import (
    RESULT_FILE,
    TCResultCollector,
)


load_dotenv()

pytest_plugins = (
    "part3_e2e.fixtures.browser",
    "part3_e2e.fixtures.auth",
    "part3_e2e.fixtures.app",
    "part3_e2e.fixtures.screenshot",
    "part3_e2e.rerun_report",
)


def pytest_collection_modifyitems(items) -> None:
    """필수 설정이 없거나 변이 실행이 비활성화되면 E2E를 건너뛴다."""

    common_names = ("LXP_ORG_NAME_SHORT",)

    role_names = {
        "learner": (
            "LXP_LEARNER_EMAIL",
            "LXP_LEARNER_PASSWORD",
        ),
        "educator": (
            "LXP_EDUCATOR_EMAIL",
            "LXP_EDUCATOR_PASSWORD",
        ),
    }

    for item in items:
        if item.get_closest_marker("e2e") is None:
            continue

        mutating_disabled = (
            item.get_closest_marker("mutating") is not None
            and os.getenv(
                "LXP_ALLOW_MUTATING_REQUESTS",
                "false",
            )
            .strip()
            .lower()
            != "true"
        )

        if mutating_disabled:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "변이 E2E 실행이 비활성화되어 있습니다. "
                        "QA 전용 계정과 데이터 초기화 여부를 확인한 뒤 "
                        "LXP_ALLOW_MUTATING_REQUESTS=true로 설정하세요."
                    )
                )
            )

        required_names = list(common_names)

        for role, names in role_names.items():
            if item.get_closest_marker(role) is not None:
                required_names.extend(names)

        missing = [name for name in required_names if not os.getenv(name, "").strip()]

        if missing:
            item.add_marker(
                pytest.mark.skip(reason=("E2E 환경변수 미설정: " + ", ".join(missing)))
            )


@pytest.fixture(
    scope="session",
    autouse=True,
)
def reset_tc_result_file():
    """테스트 실행 시작 시 이전 TC 결과 파일을 제거한다."""

    RESULT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if RESULT_FILE.exists():
        RESULT_FILE.unlink()

    yield


# course_test_data fixture는 part3_e2e/fixtures/app.py에 scope="session"으로
# 정의되어 있습니다. 이 파일에서 중복 정의하지 않습니다.
# (app.py는 pytest_plugins에 등록되어 자동 로드됩니다.)


@pytest.fixture(scope="module")
def integration_state() -> dict:
    """Journey 연속 실행 중 공유하는 테스트 상태를 저장한다.

    ⚠️ scope="module" - 테스트 파일(모듈) 단위로 새 dict를 생성하여
    동일 세션에서 다른 테스트 모듈이 실행될 때
    이전 데이터가 남아 결과를 오염시키는 문제를 방지한다.
    """
    state: dict = {}
    yield state
    state.clear()


@pytest.fixture
def tc_results(request):
    """각 Journey에서 TC 단위 실행 결과를 수집한다."""

    marker = request.node.get_closest_marker("tc_range")

    if marker is None:
        raise RuntimeError(
            f"{request.node.nodeid}에 @pytest.mark.tc_range(start, end)가 없습니다."
        )

    start_step, end_step = marker.args

    collector = TCResultCollector(
        pytest_nodeid=request.node.nodeid,
        start_step=start_step,
        end_step=end_step,
    )

    yield collector

    # 테스트 성공/실패 여부와 관계없이 fixture teardown에서
    # PASS / FAIL / NOT_RUN 결과를 파일에 저장한다.
    collector.write()
