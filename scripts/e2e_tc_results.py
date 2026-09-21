"""E2E TCResultCollector JSONL의 rerun 전체 이력을 TC 단위로 집계한다.

공식 QA 정책:
- 한 번이라도 FAIL한 TC는 rerun에서 PASS해도 최종 Sheet/Jira 판정은 FAIL이다.
- final_status에는 실제 마지막 attempt 상태를 별도로 보존한다.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


STATUS_TO_SHEET = {
    "PASS": "Pass",
    "FAIL": "Fail",
    "NOT_RUN": "Not Tested",
}

EXCLUDED_STEPS = {12, 14, 68}


def _attempt_number(payload: dict[str, Any], result: dict[str, Any]) -> int:
    raw = result.get("execution_attempt", payload.get("execution_attempt", 0))
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def load_final_tc_results(path: Path) -> dict[str, dict[str, Any]]:
    """JSONL 전체 attempt를 읽어 TC별 공식 결과와 실제 마지막 상태를 반환한다.

    반환 예:
    {
        "E2E-ALL-060": {
            "status": "FAIL",
            "final_status": "PASS",
            "rerun_recovered": True,
            "attempts": [...],
        }
    }
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"E2E TC 결과 파일이 없습니다: {path}. "
            "통합 테스트가 tc_results fixture를 실제로 사용하고 있는지 확인하세요."
        )

    attempts_by_tc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    nodeid_by_tc: dict[str, str] = {}

    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"E2E TC JSONL 파싱 실패 line={line_no}: {exc}"
                ) from exc

            nodeid = str(payload.get("pytest_nodeid") or "").strip()
            if not nodeid:
                raise ValueError(
                    f"pytest_nodeid가 없는 E2E TC 결과: line={line_no}"
                )

            for result in list(payload.get("results") or []):
                tc_id = str(result.get("tc_id") or "").strip()
                if not tc_id:
                    continue

                previous_nodeid = nodeid_by_tc.setdefault(tc_id, nodeid)
                if previous_nodeid != nodeid:
                    raise ValueError(
                        "동일 TC ID가 서로 다른 pytest nodeid에서 수집되었습니다: "
                        f"{tc_id}: {previous_nodeid!r}, {nodeid!r}"
                    )

                enriched = dict(result)
                enriched["pytest_nodeid"] = (
                    str(result.get("pytest_nodeid") or nodeid).strip()
                )
                enriched["execution_attempt"] = _attempt_number(payload, result)
                enriched["_line_no"] = line_no
                attempts_by_tc[tc_id].append(enriched)

    final: dict[str, dict[str, Any]] = {}

    for tc_id, attempts in attempts_by_tc.items():
        ordered = sorted(
            attempts,
            key=lambda item: (
                int(item.get("execution_attempt") or 0),
                int(item.get("_line_no") or 0),
            ),
        )
        latest = dict(ordered[-1])
        latest.pop("_line_no", None)

        statuses = [
            str(item.get("status") or "NOT_RUN").strip().upper()
            for item in ordered
        ]
        had_failure = "FAIL" in statuses
        final_status = statuses[-1]
        rerun_recovered = had_failure and final_status == "PASS"

        # 한 번이라도 FAIL했다면 공식 QA 결과는 FAIL 유지.
        if had_failure:
            effective_status = "FAIL"
        elif "PASS" in statuses:
            effective_status = "PASS"
        else:
            effective_status = "NOT_RUN"

        cleaned_attempts: list[dict[str, Any]] = []
        for item in ordered:
            cleaned = dict(item)
            cleaned.pop("_line_no", None)
            cleaned_attempts.append(cleaned)

        # Jira/로그에는 실제 실패 원인을 남길 수 있도록 마지막 실패 정보를 대표값으로 사용.
        failed_attempts = [
            item for item in cleaned_attempts
            if str(item.get("status") or "").strip().upper() == "FAIL"
        ]
        representative = failed_attempts[-1] if failed_attempts else latest

        merged = dict(latest)
        merged["status"] = effective_status
        merged["final_status"] = final_status
        merged["rerun_recovered"] = rerun_recovered
        merged["attempts"] = cleaned_attempts
        merged["attempt_count"] = len(cleaned_attempts)
        merged["retry_sequence"] = " -> ".join(statuses)

        if failed_attempts:
            merged["error"] = representative.get("error")
            merged["traceback"] = representative.get("traceback")
            merged["failure_attempt"] = representative.get("execution_attempt")

        final[tc_id] = merged

    return final


def validate_expected_coverage(
    results: dict[str, dict[str, Any]],
    start: int = 1,
    end: int = 98,
) -> None:
    excluded = EXCLUDED_STEPS if (start, end) == (1, 98) else set()
    expected = {
        f"E2E-ALL-{step:03d}"
        for step in range(start, end + 1)
        if step not in excluded
    }
    actual = set(results)
    missing = sorted(expected - actual)
    if missing:
        preview = ", ".join(missing[:10])
        suffix = " ..." if len(missing) > 10 else ""
        raise ValueError(
            f"E2E TC 결과 커버리지가 불완전합니다. "
            f"누락 {len(missing)}개: {preview}{suffix}"
        )

    executed = [
        tc_id
        for tc_id, result in results.items()
        if str(result.get("status") or "").strip().upper() in {"PASS", "FAIL"}
    ]
    if not executed:
        raise ValueError(
            f"E2E TC 결과 {len(expected)}개가 모두 NOT_RUN입니다. "
            "TCResultCollector.step(...)이 실제 테스트 코드에 연결되지 않았을 가능성이 높아 "
            "Google Sheet 동기화와 Jira 처리를 중단합니다."
        )
