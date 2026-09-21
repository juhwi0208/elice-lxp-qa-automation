"""pytest-rerunfailures의 재실행 결과를 JSON으로 기록한다."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


DEFAULT_RESULT_FILE = "pytest-results/e2e-rerun.json"

_rerun_nodes: set[str] = set()
_rerun_counts: dict[str, int] = {}
_final_outcomes: dict[str, str] = {}


def _result_path() -> Path:
    """rerun 결과 JSON 저장 경로를 반환한다."""
    configured = os.getenv(
        "PYTEST_RERUN_RESULT_FILE",
        DEFAULT_RESULT_FILE,
    ).strip()

    return Path(configured or DEFAULT_RESULT_FILE)


def get_execution_attempt(nodeid: str) -> int:
    """현재 pytest nodeid의 실행 attempt 번호를 반환한다.

    pytest-rerunfailures는 재실행을 결정한 시도의 call report를
    outcome='rerun'으로 먼저 남긴다. 따라서 다음 fixture 실행 시점에는
    해당 nodeid의 누적 rerun 횟수 + 1이 현재 attempt 번호가 된다.
    """
    return _rerun_counts.get(nodeid, 0) + 1


def pytest_sessionstart(session: pytest.Session) -> None:
    """이전 실행의 rerun 정보를 초기화한다."""
    del session

    _rerun_nodes.clear()
    _rerun_counts.clear()
    _final_outcomes.clear()

    result_path = _result_path()
    result_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if result_path.exists():
        result_path.unlink()


def pytest_runtest_logreport(
    report: pytest.TestReport,
) -> None:
    """
    테스트별 rerun 발생 여부와 최종 결과를 수집한다.

    pytest-rerunfailures가 재실행을 결정하면
    해당 시도의 outcome은 'rerun'으로 기록된다.
    """
    if report.when != "call":
        return

    if report.outcome == "rerun":
        _rerun_nodes.add(report.nodeid)
        _rerun_counts[report.nodeid] = _rerun_counts.get(report.nodeid, 0) + 1
        return

    if report.outcome in {
        "passed",
        "failed",
    }:
        _final_outcomes[report.nodeid] = report.outcome


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    """수집한 rerun 결과를 JSON 파일로 저장한다."""
    del session
    del exitstatus

    recovered = sum(
        1 for nodeid in _rerun_nodes if _final_outcomes.get(nodeid) == "passed"
    )

    still_failed = sum(
        1 for nodeid in _rerun_nodes if _final_outcomes.get(nodeid) == "failed"
    )

    result = {
        "retried": len(_rerun_nodes),
        "recovered": recovered,
        "still_failed": still_failed,
        "tests": [
            {
                "nodeid": nodeid,
                "rerun_count": _rerun_counts.get(nodeid, 0),
                "attempts": _rerun_counts.get(nodeid, 0) + 1,
                "final_outcome": _final_outcomes.get(
                    nodeid,
                    "unknown",
                ),
                "rerun_recovered": (_final_outcomes.get(nodeid) == "passed"),
            }
            for nodeid in sorted(_rerun_nodes)
        ],
    }

    result_path = _result_path()

    result_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "Rerun result saved: "
        f"{result_path} "
        f"(retried={result['retried']}, "
        f"recovered={result['recovered']}, "
        f"still_failed={result['still_failed']})"
    )
