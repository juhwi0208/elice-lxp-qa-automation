"""Allure API 결과와 Google Sheet TC 매핑을 검증한다.

이 스크립트는 Google Sheet를 수정하지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from googleapiclient.errors import (
    HttpError,
)

from inspect_allure_results import (
    aggregate_by_mapping_key,
    load_attempts,
    select_final_retries,
)

from tc_mapping import (
    find_duplicate_keys,
    load_api_tc_mappings,
)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--results-dir",
        default="allure-results/api",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help=("Sheet 자동화 매핑이 Allure 실행에 없으면 검증 실패 처리"),
    )

    args = parser.parse_args()

    results_dir = Path(args.results_dir)

    if not results_dir.is_dir():
        print(f"[ERROR] Allure result 디렉터리가 없습니다: {results_dir}")
        return 1

    try:
        attempts = load_attempts(results_dir)

        if not attempts:
            print("[ERROR] Allure result JSON이 없습니다.")
            return 1

        (
            final_attempts,
            retry_count,
        ) = select_final_retries(attempts)

        # raw attempt 전체를 집계해 FAIL -> rerun PASS 이력도 검증에 반영한다.
        allure_results = aggregate_by_mapping_key(attempts)

        (
            mappings,
            incomplete,
        ) = load_api_tc_mappings()

        duplicates = find_duplicate_keys(mappings)

        sheet_by_key = {mapping.key: mapping for mapping in mappings}

        allure_keys = {key for key in allure_results if key[0] and key[1]}

        sheet_keys = set(sheet_by_key)

        matched = sheet_keys & allure_keys

        sheet_missing_in_allure = sheet_keys - allure_keys

        allure_missing_in_sheet = allure_keys - sheet_keys

        print("========================================")
        print("[TC Mapping] Allure <-> Google Sheets validation")
        print("========================================")

        print(f"Allure raw files              : {len(attempts)}")

        print(f"Allure final executions       : {len(final_attempts)}")

        print(f"Allure retry attempts         : {retry_count}")

        print(f"Allure file+function keys     : {len(allure_keys)}")

        print(f"Sheet automation mappings     : {len(mappings)}")

        print(f"Matched mappings              : {len(matched)}")

        print(f"Sheet mapping not in Allure   : {len(sheet_missing_in_allure)}")

        print(f"Allure key not in Sheet       : {len(allure_missing_in_sheet)}")

        print(f"Incomplete Sheet mappings     : {len(incomplete)}")

        print(f"Duplicate Sheet mapping keys  : {len(duplicates)}")

        if incomplete:
            print("")
            print("[ERROR] 자동화인데 파일명/함수명이 비어 있는 TC")

            for item in incomplete:
                print(
                    f"  - row "
                    f"{item.sheet_row} / "
                    f"{item.tc_id} / "
                    f"file="
                    f"{item.file_name or '<empty>'}"
                    f" / function="
                    f"{item.function_name or '<empty>'}"
                )

        if duplicates:
            print("")
            print("[ERROR] 중복 파일명+함수명 매핑")

            for (
                file_name,
                function_name,
            ), items in sorted(duplicates.items()):
                tc_ids = ", ".join(
                    f"{item.tc_id}(row {item.sheet_row})" for item in items
                )

                print(f"  - {file_name}::{function_name} -> {tc_ids}")

        if sheet_missing_in_allure:
            print("")
            print("[WARN] Sheet에는 자동화로 되어 있지만 이번 Allure 실행에 없는 항목")

            for key in sorted(sheet_missing_in_allure):
                mapping = sheet_by_key[key]

                print(
                    f"  - {mapping.tc_id} / "
                    f"{key[0]}::{key[1]} "
                    f"(Sheet row "
                    f"{mapping.sheet_row})"
                )

        if allure_missing_in_sheet:
            print("")
            print("[INFO] Allure에는 있지만 TC Sheet 매핑 대상이 아닌 테스트")

            for (
                file_name,
                function_name,
            ) in sorted(allure_missing_in_sheet):
                result = allure_results[
                    (
                        file_name,
                        function_name,
                    )
                ]

                print(f"  - {file_name}::{function_name} -> {result['status']}")

        # Sheet 자체의 구조 문제는
        # 바로 오류로 판단한다.
        if incomplete or duplicates:
            print("")
            print("[ERROR] Google Sheet 매핑 구조를 먼저 수정해야 합니다.")

            return 1

        # 처음에는 strict를 사용하지 않는다.
        if args.strict and sheet_missing_in_allure:
            print("")
            print(
                "[ERROR] --strict 모드: "
                "Sheet 자동화 매핑이 "
                "Allure 실행에서 "
                "누락되었습니다."
            )

            return 1

        print("")
        print("[OK] TC mapping validation completed (read-only).")

        return 0

    except HttpError as exc:
        status = getattr(
            exc.resp,
            "status",
            "unknown",
        )

        print(f"[ERROR] Google Sheets API 요청 실패: HTTP {status}: {exc}")

        return 1

    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
