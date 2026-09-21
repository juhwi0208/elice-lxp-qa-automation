"""Google Sheet의 API TC ↔ 자동화 함수 매핑을 읽는다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from google_sheets_client import (
    read_values,
)


API_MAPPING_RANGE = "'API 테스트'!B12:N"

HEADER_ROW = 12


# B:N 범위를 읽기 때문에
# 아래 index는 B를 0으로 본다.
IDX_TC_ID = 0
IDX_RESULT = 8
IDX_AUTOMATION = 9
IDX_FILE = 11
IDX_FUNCTION = 12


@dataclass(frozen=True)
class TCMapping:
    tc_id: str
    sheet_row: int
    file_name: str
    function_name: str
    current_result: str

    @property
    def key(
        self,
    ) -> tuple[str, str]:
        return (
            self.file_name,
            self.function_name,
        )


@dataclass(frozen=True)
class IncompleteAutomationMapping:
    tc_id: str
    sheet_row: int
    file_name: str
    function_name: str


def _cell(
    row: list[str],
    index: int,
) -> str:

    if index >= len(row):
        return ""

    return str(row[index] or "").strip()


def normalize_file_name(
    value: str,
) -> str:
    """경로가 들어와도 파일명만 사용."""

    normalized = value.replace(
        "\\",
        "/",
    )

    return Path(normalized).name.strip()


def normalize_function_name(
    value: str,
) -> str:
    """parameter suffix 제거."""

    value = value.strip()

    return re.sub(
        r"\[[^\]]*\]$",
        "",
        value,
    )


def load_api_tc_mappings() -> tuple[
    list[TCMapping],
    list[IncompleteAutomationMapping],
]:
    rows = read_values(API_MAPPING_RANGE)

    mappings: list[TCMapping] = []

    incomplete: list[IncompleteAutomationMapping] = []

    # 첫 행(B12:N12)은 헤더
    for offset, row in enumerate(
        rows[1:],
        start=1,
    ):
        sheet_row = HEADER_ROW + offset

        tc_id = _cell(
            row,
            IDX_TC_ID,
        )

        automation = _cell(
            row,
            IDX_AUTOMATION,
        )

        file_name = normalize_file_name(
            _cell(
                row,
                IDX_FILE,
            )
        )

        function_name = normalize_function_name(
            _cell(
                row,
                IDX_FUNCTION,
            )
        )

        current_result = _cell(
            row,
            IDX_RESULT,
        )

        if automation != "자동화":
            continue

        # 하나의 TC에 기대결과가 여러 줄인 경우
        # TC ID/파일/함수는 첫 줄에만 존재한다.
        if not tc_id:
            continue

        if not file_name or not function_name:
            incomplete.append(
                IncompleteAutomationMapping(
                    tc_id=tc_id,
                    sheet_row=sheet_row,
                    file_name=file_name,
                    function_name=(function_name),
                )
            )

            continue

        mappings.append(
            TCMapping(
                tc_id=tc_id,
                sheet_row=sheet_row,
                file_name=file_name,
                function_name=(function_name),
                current_result=(current_result),
            )
        )

    return (
        mappings,
        incomplete,
    )


def find_duplicate_keys(
    mappings: list[TCMapping],
) -> dict[
    tuple[str, str],
    list[TCMapping],
]:

    grouped: dict[
        tuple[str, str],
        list[TCMapping],
    ] = {}

    for mapping in mappings:
        grouped.setdefault(
            mapping.key,
            [],
        ).append(mapping)

    return {key: values for key, values in grouped.items() if len(values) > 1}
