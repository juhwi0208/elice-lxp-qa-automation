"""E2E TCResultCollector 최종 결과를 Google Sheet에 동기화한다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from e2e_tc_results import (
    STATUS_TO_SHEET,
    load_final_tc_results,
    validate_expected_coverage,
)
from google_sheets_client import batch_update_values, read_values


SHEET_NAME = "전체 기능(E2E 통합)"
SHEET_RANGE = f"'{SHEET_NAME}'!A7:I105"
HEADER_ROW = 7
IDX_STEP = 0
IDX_RESULT = 6
IDX_JIRA_LINK = 8
MANUAL_ONLY_STATUSES = {"Next Event"}


def _cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index] or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result-file",
        default="artifacts/tc-results/tc_results.jsonl",
        help="TCResultCollector JSONL path",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 Google Sheet 테스트 결과(G열)를 갱신한다.",
    )
    args = parser.parse_args()

    final_results = load_final_tc_results(Path(args.result_file))
    validate_expected_coverage(final_results)

    rows = read_values(SHEET_RANGE)
    if not rows:
        raise RuntimeError(f"Google Sheet 범위를 읽지 못했습니다: {SHEET_RANGE}")

    updates: list[tuple[str, str]] = []
    matched = 0
    skipped_same = 0

    for offset, row in enumerate(rows[1:], start=1):
        step_raw = _cell(row, IDX_STEP)
        if not step_raw.isdigit():
            continue
        step = int(step_raw)
        tc_id = f"E2E-ALL-{step:03d}"
        result = final_results.get(tc_id)
        if result is None:
            continue

        status = str(result.get("status") or "").strip().upper()
        sheet_value = STATUS_TO_SHEET.get(status)
        if not sheet_value:
            raise RuntimeError(f"알 수 없는 E2E TC status: {tc_id}={status!r}")

        sheet_row = HEADER_ROW + offset
        current = _cell(row, IDX_RESULT)
        matched += 1
        if current in MANUAL_ONLY_STATUSES:
            skipped_same += 1
            print(f"[SKIP][MANUAL STATUS] {tc_id} G{sheet_row}={current!r}")
            continue
        if current == sheet_value:
            skipped_same += 1
            continue
        updates.append((f"'{SHEET_NAME}'!G{sheet_row}", sheet_value))

    print("=" * 80)
    print("[E2E TC Result Sync]")
    print("=" * 80)
    print(f"Final TC results : {len(final_results)}")
    print(f"Matched rows     : {matched}")
    print(f"Already current  : {skipped_same}")
    print(f"Pending updates  : {len(updates)}")
    print(f"Sheet write      : {'ENABLED' if args.apply else 'DISABLED'}")

    for range_name, value in updates:
        print(f"  - {range_name} -> {value}")

    if not args.apply:
        print("[DRY RUN] Google Sheet was not updated.")
        return 0

    updated_cells = batch_update_values(updates)
    if updated_cells != len(updates):
        raise RuntimeError(
            f"E2E Sheet 업데이트 수 불일치: expected={len(updates)}, actual={updated_cells}"
        )
    print(f"[UPDATED] {updated_cells} cells")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("=" * 80)
        print("[ERROR] E2E TC result sync failed")
        print("=" * 80)
        print(str(exc))
        print("=" * 80)
        sys.exit(1)
