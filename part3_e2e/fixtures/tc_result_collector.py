"""E2E TC 단위 실행 결과를 수집한다."""

from __future__ import annotations

import json
import traceback
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

import allure

from part3_e2e.rerun_report import get_execution_attempt


RESULT_DIR = Path("artifacts/tc-results")
RESULT_FILE = RESULT_DIR / "tc_results.jsonl"

SCENARIO_ID = "E2E-ALL-01"


def _now() -> str:
    """현재 UTC 시간을 ISO 8601 문자열로 반환한다."""
    return datetime.now(UTC).isoformat()


class TCResultCollector:
    """하나의 Journey 안에서 여러 TC의 실행 결과를 수집한다."""

    def __init__(
        self,
        *,
        pytest_nodeid: str,
        start_step: int,
        end_step: int,
    ) -> None:
        self.pytest_nodeid = pytest_nodeid
        self.start_step = start_step
        self.end_step = end_step
        self.execution_attempt = get_execution_attempt(pytest_nodeid)

        # 아직 실행되지 않은 TC는 기본적으로 NOT_RUN 상태로 둔다.
        self.results: dict[int, dict] = {}

        for step in range(start_step, end_step + 1):
            self.results[step] = {
                "scenario_id": SCENARIO_ID,
                "tc_id": self._tc_id(step),
                "step": step,
                "status": "NOT_RUN",
                "pytest_nodeid": pytest_nodeid,
                "execution_attempt": self.execution_attempt,
                "title": None,
                "error": None,
                "traceback": None,
                "started_at": None,
                "finished_at": None,
            }

    @staticmethod
    def _tc_id(step: int) -> str:
        """TC 식별자를 생성한다."""
        return f"E2E-ALL-{step:03d}"

    @contextmanager
    def step(
        self,
        step: int,
        title: str,
    ) -> Iterator[None]:
        """TC 하나를 실행하면서 PASS/FAIL 결과를 기록한다."""

        if step not in self.results:
            raise ValueError(
                f"현재 Journey 범위를 벗어난 TC입니다: {step} "
                f"({self.start_step}~{self.end_step})"
            )

        result = self.results[step]

        result["title"] = title
        result["started_at"] = _now()

        tc_id = self._tc_id(step)

        with allure.step(f"[{tc_id}] {title}"):
            try:
                yield

            except BaseException as exc:
                result["status"] = "FAIL"
                result["error"] = f"{type(exc).__name__}: {exc}"
                result["traceback"] = traceback.format_exc()
                result["finished_at"] = _now()

                allure.attach(
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    name=(f"{tc_id}-attempt-{self.execution_attempt}-failure"),
                    attachment_type=allure.attachment_type.JSON,
                )

                # pytest에서도 기존과 동일하게 FAIL 처리되도록
                # 예외를 다시 발생시킨다.
                raise

            else:
                result["status"] = "PASS"
                result["finished_at"] = _now()

    def write(self) -> None:
        """현재 Journey의 TC 결과를 JSONL 파일에 저장한다."""

        RESULT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "pytest_nodeid": self.pytest_nodeid,
            "scenario_id": SCENARIO_ID,
            "execution_attempt": self.execution_attempt,
            "step_range": [
                self.start_step,
                self.end_step,
            ],
            "results": list(self.results.values()),
        }

        with RESULT_FILE.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                )
            )
            file.write("\n")
