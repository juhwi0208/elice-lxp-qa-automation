"""Allure raw result를 읽어 API 테스트의 최종 실행 결과를 점검한다.

- pytest-rerunfailures로 생성된 retry는 historyId 기준으로 묶는다.
- 파라미터 테스트는 retry를 정리한 뒤 파일명+함수명 기준으로 다시 집계한다.
- Google Sheets에는 쓰지 않는 read-only 검증 스크립트다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESULT_GLOB = "*-result.json"

STATUS_ORDER = {
    "unknown": 0,
    "passed": 1,
    "skipped": 2,
    "broken": 3,
    "failed": 4,
}


@dataclass(frozen=True)
class AllureAttempt:
    source: Path
    uuid: str
    history_id: str
    name: str
    full_name: str
    file_name: str
    function_name: str
    status: str
    message: str
    trace: str
    start: int
    stop: int

    @property
    def mapping_key(self) -> tuple[str, str]:
        return self.file_name, self.function_name


def _labels_by_name(data: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}

    for item in data.get("labels", []) or []:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()

        if name and value and name not in labels:
            labels[name] = value

    return labels


def _strip_param_suffix(value: str) -> str:
    """test_x[param] -> test_x"""
    return re.sub(r"\[[^\]]*\]$", "", value.strip())


def _extract_file_and_function(
    data: dict[str, Any],
) -> tuple[str, str]:
    labels = _labels_by_name(data)

    full_name = str(data.get("fullName") or "").strip()

    name = _strip_param_suffix(str(data.get("name") or "").strip())

    # 함수명
    function_name = ""

    if "#" in full_name:
        function_name = _strip_param_suffix(full_name.rsplit("#", 1)[1])

    if not function_name:
        function_name = name

    # 파일명
    #
    # allure-pytest가 자동으로 넣는 suite는
    # 일반적으로 Python test module 이름이다.
    suite = str(labels.get("suite") or "").strip()

    if suite:
        suite = suite.rsplit(".", 1)[-1]

    file_name = f"{suite}.py" if suite else ""

    # suite가 없을 때 fallback
    if not file_name and full_name:
        module_part = full_name.split(
            "#",
            1,
        )[0]

        module_name = module_part.rsplit(
            ".",
            1,
        )[-1]

        if module_name.startswith("test_"):
            file_name = f"{module_name}.py"

    return file_name, function_name


def load_attempts(
    results_dir: Path,
) -> list[AllureAttempt]:
    attempts: list[AllureAttempt] = []

    for path in sorted(results_dir.glob(RESULT_GLOB)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(f"Allure result JSON 읽기 실패: {path}: {exc}") from exc

        (
            file_name,
            function_name,
        ) = _extract_file_and_function(data)

        status_details = data.get("statusDetails") or {}

        history_id = str(data.get("historyId") or "").strip()

        uuid = str(data.get("uuid") or path.stem).strip()

        # historyId가 없는 결과끼리
        # 잘못 합쳐지지 않도록 uuid 사용
        retry_key = history_id or f"uuid:{uuid}"

        attempts.append(
            AllureAttempt(
                source=path,
                uuid=uuid,
                history_id=retry_key,
                name=str(data.get("name") or "").strip(),
                full_name=str(data.get("fullName") or "").strip(),
                file_name=file_name,
                function_name=function_name,
                status=str(data.get("status") or "unknown").strip().lower(),
                message=str(status_details.get("message") or "").strip(),
                trace=str(status_details.get("trace") or "").strip(),
                start=int(data.get("start") or 0),
                stop=int(data.get("stop") or 0),
            )
        )

    return attempts


def select_final_retries(
    attempts: list[AllureAttempt],
) -> tuple[list[AllureAttempt], int]:
    """동일 historyId 중 마지막 attempt만 선택한다."""

    groups: dict[
        str,
        list[AllureAttempt],
    ] = defaultdict(list)

    for attempt in attempts:
        groups[attempt.history_id].append(attempt)

    final_attempts: list[AllureAttempt] = []

    retry_count = 0

    for group in groups.values():
        retry_count += max(
            0,
            len(group) - 1,
        )

        final_attempt = max(
            group,
            key=lambda item: (
                item.stop,
                item.start,
                str(item.source),
            ),
        )

        final_attempts.append(final_attempt)

    return (
        final_attempts,
        retry_count,
    )


def aggregate_by_mapping_key(
    attempts: list[AllureAttempt],
) -> dict[
    tuple[str, str],
    dict[str, Any],
]:
    """파일명+함수명 기준으로 최종 결과와 rerun 이력을 함께 집계한다."""

    retry_groups: dict[
        str,
        list[AllureAttempt],
    ] = defaultdict(list)

    for attempt in attempts:
        retry_groups[attempt.history_id].append(attempt)

    executions_by_key: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for group in retry_groups.values():
        ordered = sorted(
            group,
            key=lambda item: (
                item.stop,
                item.start,
                str(item.source),
            ),
        )

        final_attempt = ordered[-1]

        had_previous_failure = any(
            item.status in {"failed", "broken"} for item in ordered[:-1]
        )

        rerun_recovered = had_previous_failure and final_attempt.status == "passed"

        executions_by_key[final_attempt.mapping_key].append(
            {
                "final_attempt": final_attempt,
                "attempts": ordered,
                "rerun_recovered": rerun_recovered,
            }
        )

    aggregated: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for key, executions in executions_by_key.items():
        final_attempts = [execution["final_attempt"] for execution in executions]

        worst_final = max(
            final_attempts,
            key=lambda item: STATUS_ORDER.get(
                item.status,
                0,
            ),
        )

        rerun_recovered = any(execution["rerun_recovered"] for execution in executions)

        # FAIL → PASS도 공식 QA 결과는 Fail로 취급한다.
        effective_status = "failed" if rerun_recovered else worst_final.status

        all_attempts = [
            attempt for execution in executions for attempt in execution["attempts"]
        ]

        retry_sequences = [
            " -> ".join(attempt.status.upper() for attempt in execution["attempts"])
            for execution in executions
            if len(execution["attempts"]) > 1
        ]

        aggregated[key] = {
            # QA 공식 판정
            "status": effective_status,
            # 실제 마지막 pytest/Allure 결과
            "final_status": worst_final.status,
            "cases": len(executions),
            "attempts": all_attempts,
            "rerun_recovered": rerun_recovered,
            "retry_sequences": retry_sequences,
        }

    return aggregated


def print_summary(
    attempts: list[AllureAttempt],
    final_attempts: list[AllureAttempt],
    retry_count: int,
    aggregated: dict[
        tuple[str, str],
        dict[str, Any],
    ],
    show_failures: bool,
) -> None:

    final_counts = Counter(item.status for item in final_attempts)

    function_counts = Counter(item["status"] for item in aggregated.values())
    rerun_recovered_count = sum(
        1 for item in aggregated.values() if item.get("rerun_recovered")
    )

    missing_identity = [
        item for item in final_attempts if not item.file_name or not item.function_name
    ]

    print("========================================")
    print("[Allure] API raw result inspection")
    print("========================================")

    print(f"Raw result files : {len(attempts)}")

    print(f"Unique executions: {len(final_attempts)}")

    print(f"Retries          : {retry_count}")
    print(f"  Rerun Passed / Fail 판정: {rerun_recovered_count}")

    print("")

    print("[Final pytest executions]")

    for status in (
        "passed",
        "failed",
        "broken",
        "skipped",
        "unknown",
    ):
        print(f"  {status:<7}: {final_counts.get(status, 0)}")

    print("")
    print("[After file+function aggregation]")

    print(f"  Functions: {len(aggregated)}")

    for status in (
        "passed",
        "failed",
        "broken",
        "skipped",
        "unknown",
    ):
        print(f"  {status:<7}: {function_counts.get(status, 0)}")

    parameterized = [
        (
            key,
            value["cases"],
        )
        for key, value in aggregated.items()
        if value["cases"] > 1
    ]

    if parameterized:
        print("")
        print(f"[INFO] Parameterized/multi-case functions: {len(parameterized)}")

        for (
            file_name,
            function_name,
        ), cases in sorted(parameterized):
            print(f"  - {file_name}::{function_name} ({cases} cases)")

    if missing_identity:
        print("")
        print(f"[ERROR] file/function 추출 실패: {len(missing_identity)}")

        for item in missing_identity[:20]:
            print(f"  - {item.source.name}: fullName={item.full_name!r}")

    if show_failures:
        failed = [
            (
                key,
                value,
            )
            for key, value in aggregated.items()
            if value["status"]
            in {
                "failed",
                "broken",
            }
        ]

        if failed:
            print("")
            print("[Failed/Broken functions]")

            for (
                file_name,
                function_name,
            ), value in sorted(failed):
                representative = max(
                    value["attempts"],
                    key=lambda item: STATUS_ORDER.get(
                        item.status,
                        0,
                    ),
                )

                print(f"  - {file_name}::{function_name} -> {value['status']}")

                if representative.message:
                    first_line = representative.message.splitlines()[0]

                    print(f"    message: {first_line[:300]}")

    if missing_identity:
        raise RuntimeError("일부 Allure 결과에서 파일명/함수명을 추출하지 못했습니다.")


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--results-dir",
        default="allure-results/api",
        help=("Allure raw result 디렉터리"),
    )

    parser.add_argument(
        "--show-failures",
        action="store_true",
        help=("failed/broken 함수와 에러 첫 줄을 출력"),
    )

    args = parser.parse_args()

    results_dir = Path(args.results_dir)

    if not results_dir.is_dir():
        print(f"[ERROR] Allure result 디렉터리를 찾을 수 없습니다: {results_dir}")
        return 1

    try:
        attempts = load_attempts(results_dir)

        if not attempts:
            print(f"[ERROR] Allure result 파일이 없습니다: {results_dir}/{RESULT_GLOB}")
            return 1

        (
            final_attempts,
            retry_count,
        ) = select_final_retries(attempts)

        aggregated = aggregate_by_mapping_key(attempts)

        print_summary(
            attempts,
            final_attempts,
            retry_count,
            aggregated,
            show_failures=(args.show_failures),
        )

        return 0

    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
