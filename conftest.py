"""전체 테스트 실행 순서와 프로세스 상태를 격리하는 pytest 설정."""

from __future__ import annotations


from collections.abc import Iterator

import pytest

from test_support.cleanup import CleanupRegistry


def _is_api_test(request: pytest.FixtureRequest) -> bool:
    path = getattr(request.node, "path", None)
    if path is None:
        return False
    return "part1_api_automation" in path.parts


@pytest.fixture(autouse=True)
def isolate_api_runtime_state(request: pytest.FixtureRequest) -> Iterator[None]:
    """API 호출 수와 5xx 중단 상태가 다음 테스트로 전파되지 않게 한다.

    한 테스트 안에서는 기존 안전 정책대로 5xx 이후 호출이 차단된다. 테스트가
    끝나면 성공·실패 여부와 관계없이 프로세스 상태를 초기화한다.
    """
    if not _is_api_test(request):
        yield
        return

    from part1_api_automation.utils import api_client

    api_client.reset_safety_state()
    try:
        yield
    finally:
        api_client.reset_safety_state()


@pytest.fixture
def cleanup_registry() -> Iterator[CleanupRegistry]:
    """테스트 중 등록한 외부 데이터를 성공·실패와 무관하게 정리한다."""
    registry = CleanupRegistry()
    try:
        yield registry
    finally:
        registry.run()
