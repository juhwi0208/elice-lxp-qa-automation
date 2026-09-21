"""Jenkins에서 Google Sheets API 연결 상태를 검증한다."""

from __future__ import annotations

import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TEST_RANGE = "'API 테스트'!A1:N5"


def main() -> int:
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")

    if not credentials_path:
        print("[ERROR] GOOGLE_APPLICATION_CREDENTIALS 환경변수가 설정되지 않았습니다.")
        return 1

    if not spreadsheet_id:
        print("[ERROR] GOOGLE_SPREADSHEET_ID 환경변수가 설정되지 않았습니다.")
        return 1

    if not os.path.isfile(credentials_path):
        print("[ERROR] Google Service Account 인증 파일을 찾을 수 없습니다.")
        return 1

    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=[GOOGLE_SHEETS_SCOPE],
        )

        service = build(
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
        )

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=TEST_RANGE,
            )
            .execute()
        )

        values = result.get("values", [])

        print("========================================")
        print("[OK] Google Sheets API connection succeeded")
        print(f"[OK] Test range: {TEST_RANGE}")
        print(f"[OK] Retrieved rows: {len(values)}")
        print("========================================")

        # 실제 TC 내용 전체를 Jenkins 로그에 노출하지 않는다.
        if values:
            print("[OK] Spreadsheet data is readable.")
        else:
            print("[WARN] Connection succeeded, but the test range is empty.")

        return 0

    except HttpError as exc:
        status = getattr(exc.resp, "status", "unknown")

        print("========================================")
        print("[ERROR] Google Sheets API request failed")
        print(f"[ERROR] HTTP status: {status}")
        print(f"[ERROR] Detail: {exc}")
        print("========================================")

        return 1

    except Exception as exc:
        print("========================================")
        print("[ERROR] Google Sheets connection test failed")
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        print("========================================")

        return 1


if __name__ == "__main__":
    sys.exit(main())
