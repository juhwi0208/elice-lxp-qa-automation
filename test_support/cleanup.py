"""테스트가 생성한 외부 데이터를 실패 여부와 무관하게 정리한다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


CleanupCallback = Callable[[], None]


@dataclass(frozen=True)
class CleanupAction:
    key: str
    description: str
    callback: CleanupCallback


class CleanupError(RuntimeError):
    """모든 정리를 시도한 뒤 실패 항목을 한 번에 보고한다."""


class CleanupRegistry:
    """생성 역순으로 실행되는 테스트 단위 cleanup 작업 목록."""

    def __init__(self) -> None:
        self._actions: list[CleanupAction] = []
        self._keys: set[str] = set()

    def add(
        self,
        *,
        key: str,
        description: str,
        callback: CleanupCallback,
    ) -> None:
        """중복 key는 한 번만 등록해 동일 데이터의 중복 삭제를 막는다."""
        if not key.strip():
            raise ValueError("cleanup key는 비어 있을 수 없습니다.")
        if key in self._keys:
            return

        self._actions.append(CleanupAction(key, description, callback))
        self._keys.add(key)

    def run(self) -> None:
        """모든 작업을 역순 실행하고 실패가 있어도 나머지 정리를 계속한다."""
        failures: list[str] = []

        while self._actions:
            action = self._actions.pop()
            self._keys.discard(action.key)
            try:
                action.callback()
            except Exception as exc:  # cleanup은 다음 작업을 계속해야 한다.
                failures.append(
                    f"{action.description}: {type(exc).__name__}: {exc}"
                )

        if failures:
            details = "\n".join(f"- {failure}" for failure in failures)
            raise CleanupError(f"테스트 데이터 정리에 실패했습니다.\n{details}")

    def __len__(self) -> int:
        return len(self._actions)
