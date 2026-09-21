"""Google Sheets API 인증/읽기/갱신 공통 클라이언트."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build


GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class GoogleSheetsConfigError(RuntimeError):
    """Google Sheets 환경 설정 오류."""


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise GoogleSheetsConfigError(f"{name} 환경변수가 설정되지 않았습니다.")
    return value


def build_sheets_service() -> Any:
    credentials_path = Path(_required_env("GOOGLE_APPLICATION_CREDENTIALS"))
    if not credentials_path.is_file():
        raise GoogleSheetsConfigError(
            f"Google Service Account 인증 파일을 찾을 수 없습니다: {credentials_path}"
        )

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=[GOOGLE_SHEETS_SCOPE],
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def get_spreadsheet_id() -> str:
    return _required_env("GOOGLE_SPREADSHEET_ID")


def read_values(range_name: str) -> list[list[str]]:
    service = build_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=get_spreadsheet_id(), range=range_name)
        .execute()
    )
    return result.get("values", []) or []


def update_value(range_name: str, value: str) -> int:
    service = build_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=get_spreadsheet_id(),
            range=range_name,
            valueInputOption="RAW",
            body={"values": [[value]]},
        )
        .execute()
    )
    return int(result.get("updatedCells") or 0)


def batch_update_values(updates: list[tuple[str, str]]) -> int:
    """여러 단일 셀 값을 한 번의 Sheets batchUpdate로 갱신한다."""
    if not updates:
        return 0

    service = build_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=get_spreadsheet_id(),
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": range_name, "values": [[value]]}
                    for range_name, value in updates
                ],
            },
        )
        .execute()
    )
    return int(result.get("totalUpdatedCells") or 0)


def append_values(
    range_name: str,
    values: list[list[str]],
) -> int:
    """지정 범위의 다음 빈 행에 값을 추가하고 갱신된 셀 수를 반환한다."""
    if not values:
        return 0

    service = build_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=get_spreadsheet_id(),
            range=range_name,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        )
        .execute()
    )
    updates = result.get("updates") or {}
    return int(updates.get("updatedCells") or 0)
