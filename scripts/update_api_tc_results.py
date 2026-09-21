"""Allure API 결과를 Google Sheet의 API TC 결과(J열)에 동기화한다.

기본 실행은 Dry-run이다.
실제 반영은 --apply 옵션을 명시했을 때만 수행한다.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from google_sheets_client import (
    build_sheets_service,
    get_spreadsheet_id,
)
from inspect_allure_results import (
    aggregate_by_mapping_key,
    load_attempts,
    select_final_retries,
)
from tc_mapping import load_api_tc_mappings


STATUS_TO_SHEET = {
    "passed": "Pass",
    "failed": "Fail",
    "skipped": "Not Tested",
    "broken": "Blocked",
}

# Next Event는 Out of Scope 등 QA 담당자가 직접 판단하는 수동 상태다.
# Jenkins 자동 실행 결과로 덮어쓰지 않는다.
MANUAL_ONLY_STATUSES = {"Next Event"}

DEFAULT_RESULTS_DIR = Path("allure-results/api")
API_SHEET_NAME = "API 테스트"


def _load_sheet_mappings():
    """tc_mapping.py 반환 형식 차이를 흡수한다."""
    loaded = load_api_tc_mappings()

    if isinstance(loaded, tuple):
        mappings = loaded[0]
        incomplete = loaded[1] if len(loaded) > 1 else []
    else:
        mappings = loaded
        incomplete = []

    return list(mappings), list(incomplete)


def _group_sheet_mappings(mappings):
    grouped = defaultdict(list)

    for mapping in mappings:
        grouped[mapping.key].append(mapping)

    return dict(grouped)


def _status_of(result) -> str:
    """aggregate_by_mapping_key 결과의 status를 안전하게 읽는다."""
    status = getattr(result, "status", None)

    if status is None and isinstance(result, dict):
        status = result.get("status")

    return str(status or "unknown").lower()


def _normalize_current_result(value) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _batch_update_results(update_candidates) -> int:
    """업데이트 후보를 Google Sheets J열에 한 번에 반영한다."""
    if not update_candidates:
        return 0

    service = build_sheets_service()
    spreadsheet_id = get_spreadsheet_id()

    data = []

    for mapping, sheet_status, _, _ in update_candidates:
        data.append(
            {
                "range": (f"'{API_SHEET_NAME}'!J{mapping.sheet_row}"),
                "values": [[sheet_status]],
            }
        )

    body = {
        "valueInputOption": "RAW",
        "data": data,
    }

    response = (
        service.spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body,
        )
        .execute()
    )

    return int(
        response.get(
            "totalUpdatedCells",
            0,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Allure API 최종 결과를 Google Sheet API TC "
            "테스트 결과(J열)에 동기화합니다. "
            "기본은 Dry-run이며 --apply일 때만 실제 수정합니다."
        )
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Allure raw result 디렉터리",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 Google Sheet J열을 업데이트합니다.",
    )
    args = parser.parse_args()

    attempts = load_attempts(args.results_dir)
    final_results, retry_attempts = select_final_retries(attempts)
    # raw attempt 전체를 집계해야 FAIL -> rerun PASS 이력을 보존할 수 있다.
    allure_by_key = aggregate_by_mapping_key(attempts)

    mappings, incomplete = _load_sheet_mappings()
    sheet_by_key = _group_sheet_mappings(mappings)

    duplicate_keys = {
        key: items for key, items in sheet_by_key.items() if len(items) > 1
    }

    update_candidates = []
    unchanged = []
    missing_in_allure = []
    unknown_status = []

    for key, items in sorted(sheet_by_key.items()):
        # 현재 정책:
        # 하나의 파일명+함수명이 여러 TC에 연결되어 있으면
        # 잘못된 PASS/FAIL 전파를 막기 위해 모두 자동 업데이트에서 제외한다.
        if key in duplicate_keys:
            continue

        mapping = items[0]
        allure_result = allure_by_key.get(key)

        if allure_result is None:
            missing_in_allure.append(mapping)
            continue

        allure_status = _status_of(allure_result)
        sheet_status = STATUS_TO_SHEET.get(allure_status)

        if sheet_status is None:
            unknown_status.append(
                (
                    mapping,
                    allure_status,
                )
            )
            continue

        current_result = _normalize_current_result(
            getattr(
                mapping,
                "current_result",
                "",
            )
        )

        if current_result in MANUAL_ONLY_STATUSES:
            unchanged.append(
                (
                    mapping,
                    current_result,
                )
            )
            print(
                f"[SKIP][MANUAL STATUS] "
                f"{mapping.tc_id} "
                f"J{mapping.sheet_row}={current_result!r}"
            )
            continue

        if current_result == sheet_status:
            unchanged.append(
                (
                    mapping,
                    sheet_status,
                )
            )
            continue

        update_candidates.append(
            (
                mapping,
                sheet_status,
                allure_status,
                allure_result,
            )
        )

    mode = "APPLY" if args.apply else "DRY RUN"

    print("=" * 60)
    print(f"[API TC Result Sync - {mode}]")
    print("=" * 60)
    print(f"Allure final executions      : {len(final_results)}")
    print(f"Allure retry attempts        : {retry_attempts}")
    print(f"Allure file+function keys    : {len(allure_by_key)}")
    print(f"Sheet automation mappings    : {len(mappings)}")
    print(f"Update candidates            : {len(update_candidates)}")
    print(f"Already up-to-date           : {len(unchanged)}")
    print(f"Duplicate mapping keys       : {len(duplicate_keys)}")
    print(f"Sheet mapping not in Allure  : {len(missing_in_allure)}")
    print(f"Incomplete Sheet mappings    : {len(incomplete)}")
    print(f"Unknown statuses             : {len(unknown_status)}")

    counts = defaultdict(int)

    for _, sheet_status, _, _ in update_candidates:
        counts[sheet_status] += 1

    print("")
    print("[Result preview]")
    for name in (
        "Pass",
        "Fail",
        "Not Tested",
    ):
        print(f"  {name:<10}: {counts[name]}")

    if update_candidates:
        print("")
        print("[UPDATE TARGETS]")

        for (
            mapping,
            sheet_status,
            allure_status,
            allure_result,
        ) in update_candidates:
            current_result = (
                _normalize_current_result(
                    getattr(
                        mapping,
                        "current_result",
                        "",
                    )
                )
                or "(empty)"
            )

            rerun_label = (
                " [RERUN PASS]" if allure_result.get("rerun_recovered") else ""
            )

            print(
                f"  - {mapping.tc_id} "
                f"(J{mapping.sheet_row}) "
                f"{current_result} -> {sheet_status}"
                f"{rerun_label} "
                f"[{mapping.file_name}::{mapping.function_name}]"
            )

    if duplicate_keys:
        print("")
        print("[SKIP] 중복 파일명+함수명 매핑 (자동 업데이트하지 않음)")

        for (
            file_name,
            function_name,
        ), items in sorted(duplicate_keys.items()):
            tc_info = ", ".join(f"{item.tc_id}(row {item.sheet_row})" for item in items)

            print(f"  - {file_name}::{function_name} -> {tc_info}")

    if missing_in_allure:
        print("")
        print("[SKIP] Sheet에는 자동화로 되어 있지만 이번 Allure 결과에 없는 TC")

        for mapping in missing_in_allure:
            print(
                f"  - {mapping.tc_id} "
                f"(row {mapping.sheet_row}) / "
                f"{mapping.file_name}::{mapping.function_name}"
            )

    if incomplete:
        print("")
        print("[ERROR] 자동화 대상이지만 파일명/함수명이 불완전한 TC")

        for item in incomplete:
            tc_id = getattr(
                item,
                "tc_id",
                "?",
            )
            sheet_row = getattr(
                item,
                "sheet_row",
                "?",
            )

            print(f"  - {tc_id} (row {sheet_row})")

    if unknown_status:
        print("")
        print("[SKIP] 자동 변환 규칙이 없는 Allure 상태")

        for mapping, status in unknown_status:
            print(f"  - {mapping.tc_id} (row {mapping.sheet_row}) -> {status}")

    # 파일명/함수명이 비어 있는 자동화 TC는 구조 오류다.
    # 실제 쓰기 모드에서는 데이터 변경 전에 즉시 중단한다.
    if incomplete:
        print("")
        print("[ABORT] Sheet 구조 오류가 있어 Google Sheet를 수정하지 않았습니다.")
        return 1

    if not args.apply:
        print("")
        print("=" * 60)
        print("[DRY RUN] Google Sheet 데이터는 수정하지 않았습니다.")
        print("실제 반영 시 --apply 옵션을 사용하세요.")
        print("=" * 60)
        return 0

    updated_cells = _batch_update_results(update_candidates)

    print("")
    print("=" * 60)
    print("[APPLY] Google Sheet 업데이트 완료")
    print(f"Requested updates : {len(update_candidates)}")
    print(f"Updated cells     : {updated_cells}")
    print("=" * 60)

    if updated_cells != len(update_candidates):
        print("[WARN] 요청한 업데이트 수와 실제 수정된 셀 수가 다릅니다.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
