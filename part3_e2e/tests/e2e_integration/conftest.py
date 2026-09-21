"""e2e integration 디렉터리 전용 pytest fixture."""

from __future__ import annotations

import pytest

from part3_e2e.config import CourseTestData, load_course_test_data


@pytest.fixture(scope="session")
def course_test_data() -> CourseTestData:
    """학습과목 E2E에서 사용할 QA 전용 더미 데이터를 로드한다."""
    return load_course_test_data()


@pytest.fixture
def integration_state() -> dict:
    """단계 간 공유 상태(생성 ID, 원본 값, 복구 플래그)를 저장하는 빈 딕셔너리.

    테스트 본문에서 다음처럼 사용한다:
        integration_state["schedule_id"] = created_id
    teardown에서 자동 정리는 각 테스트 내 try/finally 또는
    cleanup_registry fixture를 함께 사용하도록 한다.
    """
    return {}
