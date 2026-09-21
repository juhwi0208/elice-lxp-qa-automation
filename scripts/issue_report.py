"""Google Sheet '이슈 리포트' 자동 기록 공통 모듈.

시트 구조(A:P):
A NO
B TC ID
C 이슈위치
D 이슈명
E 테스트 유형
F 사전조건
G 재현순서
H 기대결과
I 이슈 요약
J 실제 결과
K 추가설명 / 로그 기록 01
L 추가설명 / 로그 기록 02
M 추가설명 / 로그 기록 03
N Jira 이슈 키
O Jira 이슈 링크
P 발견 일시
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from google_sheets_client import append_values, read_values, update_value


SHEET_NAME = "이슈 리포트"
REPORT_RANGE = f"'{SHEET_NAME}'!A:P"
KST = timezone(timedelta(hours=9), name="KST")


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text or "", flags=re.IGNORECASE | re.DOTALL)
    return str(match.group(1) or "").strip() if match else ""


def _expected_status(expected: str) -> str:
    return _first_match(r"_result\.status\s*=\s*['\"]?(ok|fail)", expected)


def _actual_status(actual: str) -> str:
    return _first_match(
        r"['\"]status['\"]\s*:\s*['\"](ok|fail)['\"]",
        actual,
    )


def _actual_status_code(actual: str) -> str:
    return _first_match(
        r"['\"]status_code['\"]\s*:\s*(\d{3})",
        actual,
    )


def _expected_fail_code(expected: str) -> str:
    value = _first_match(
        r"fail_code\s*=\s*['\"]?([A-Za-z0-9_-]+)",
        expected,
    )
    if value:
        return value

    # TC 문장에 fail_code= 표기가 없어도 대표 오류명이 직접 쓰인 경우를 지원한다.
    known = (
        "insufficient_permission",
        "resource_not_found",
        "invalid_parameter",
        "unauthorized",
        "forbidden",
    )
    lowered = (expected or "").lower()
    for code in known:
        if code in lowered:
            return code
    return ""


def _actual_fail_code(actual: str) -> str:
    return _first_match(
        r"['\"]fail_code['\"]\s*:\s*['\"]([^'\"]+)['\"]",
        actual,
    )


def _assertion_values(actual: str) -> tuple[str, str]:
    """pytest의 `assert 'actual' == 'expected'` 형태에서 값을 추출한다."""
    match = re.search(
        r"assert\s+['\"]([^'\"]+)['\"]\s*==\s*['\"]([^'\"]+)['\"]",
        actual or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return "", ""
    return str(match.group(1)), str(match.group(2))


def _impact_hint(title: str, expected: str, actual: str) -> str:
    text = f"{title} {expected} {actual}".lower()

    if any(token in text for token in ("비밀글", "비공개", "권한", "permission")):
        if "status': 'ok" in text or 'status": "ok' in text or "status=ok" in text:
            return "권한이 없는 사용자에게 데이터가 노출되거나 허용되지 않은 동작이 수행될 수 있습니다."
        return "권한 처리 결과가 요구사항과 달라 접근제어 동작을 신뢰하기 어렵습니다."

    if any(token in text for token in ("수정", "변경", "edit", "update")):
        return "사용자가 정상적인 수정/변경 작업을 완료하지 못하거나 잘못된 요청이 처리될 수 있습니다."

    if any(token in text for token in ("조회", "get", "read")):
        return "조회 결과가 요구사항과 달라 잘못된 데이터가 노출되거나 정상 조회가 차단될 수 있습니다."

    return "기대 동작과 실제 동작이 달라 해당 기능의 정상 사용에 영향을 줄 수 있습니다."


def build_issue_summary(
    *,
    title: str,
    expected: str,
    actual: str,
) -> str:
    """AI 없이 기대결과와 실제 실패 결과의 차이를 사람이 읽기 쉽게 요약한다.

    원인을 확정하지 않는다. 확인 가능한 응답 차이와 영향만 기록하고,
    내부 원인은 항상 '확인 필요' 수준으로 표현한다.
    """
    expected_status = _expected_status(expected)
    actual_status = _actual_status(actual)
    status_code = _actual_status_code(actual)
    expected_code = _expected_fail_code(expected)
    actual_code = _actual_fail_code(actual)
    assertion_actual, assertion_expected = _assertion_values(actual)

    actual_bits: list[str] = []
    if actual_status:
        actual_bits.append(f"status={actual_status}")
    if status_code:
        actual_bits.append(f"status_code={status_code}")
    if actual_code:
        actual_bits.append(f"fail_code={actual_code}")
    actual_brief = ", ".join(actual_bits)

    if expected_status == "fail" and actual_status == "ok":
        problem = "거부되어야 하는 요청이 정상 처리되었습니다."
        difference = (
            f"기대: status=fail"
            + (f", fail_code={expected_code}" if expected_code else "")
            + f" / 실제: {actual_brief or '성공 응답'}"
        )
    elif expected_status == "ok" and actual_status == "fail":
        problem = "정상 처리되어야 하는 요청이 오류로 실패했습니다."
        difference = "기대: status=ok" + f" / 실제: {actual_brief or '실패 응답'}"
    elif expected_code and actual_code and expected_code != actual_code:
        problem = "요청은 실패했지만 반환된 오류 코드가 기대값과 다릅니다."
        difference = f"기대: fail_code={expected_code} / 실제: fail_code={actual_code}"
    elif assertion_actual and assertion_expected:
        problem = "검증 대상 값이 기대값과 다르게 반환되었습니다."
        difference = f"기대: {assertion_expected} / 실제: {assertion_actual}"
    elif actual_status == "fail":
        problem = "API 요청이 실패하여 기대 동작을 만족하지 못했습니다."
        difference = f"실제: {actual_brief or '실패 응답'}"
    else:
        problem = "자동화 검증에서 기대결과와 실제 동작의 불일치가 확인되었습니다."
        difference = "세부 차이는 기대결과와 실제 결과를 확인해야 합니다."

    impact = _impact_hint(title, expected, actual)

    return (
        f"문제: {problem}\n"
        f"차이: {difference}\n"
        f"영향: {impact}\n"
        "원인: 테스트 결과만으로 내부 원인은 확정할 수 없어 개발 로그/서버 처리 확인이 필요합니다."
    )


@dataclass(frozen=True)
class IssueReportRow:
    tc_id: str
    location: str
    issue_name: str
    test_type: str
    precondition: str
    reproduction_steps: str
    expected: str
    issue_summary: str
    actual: str
    log_01: str
    log_02: str
    log_03: str
    jira_key: str
    jira_link: str
    discovered_at: str = ""

    def values(self, no: int) -> list[str]:
        discovered_at = self.discovered_at or datetime.now(KST).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return [
            str(no),
            self.tc_id,
            self.location,
            self.issue_name,
            self.test_type,
            self.precondition,
            self.reproduction_steps,
            self.expected,
            self.issue_summary,
            self.actual,
            self.log_01,
            self.log_02,
            self.log_03,
            self.jira_key,
            self.jira_link,
            discovered_at,
        ]


def _cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index] or "").strip()


def _next_no(rows: list[list[str]]) -> int:
    numbers: list[int] = []
    for row in rows:
        value = _cell(row, 0)
        if value.isdigit():
            numbers.append(int(value))
    return max(numbers, default=0) + 1


def _find_jira_key_row(
    rows: list[list[str]],
    jira_key: str,
) -> tuple[int, list[str]] | None:
    """Jira key가 있는 이슈 리포트의 실제 시트 행 번호와 행 데이터를 찾는다.

    REPORT_RANGE가 A:P 전체 범위이므로 read_values() 결과의 첫 행은 시트 1행이다.
    A:P 기준 Jira 이슈 키는 N열(index 13), 이슈 요약은 I열(index 8)이다.
    """
    if not jira_key:
        return None

    for sheet_row, row in enumerate(rows, start=1):
        if _cell(row, 13) == jira_key:
            return sheet_row, row
    return None


def _backfill_issue_summary(
    *,
    report: IssueReportRow,
    sheet_row: int,
    existing_row: list[str],
) -> bool:
    """기존 이슈 리포트 행의 빈 I열(이슈 요약)만 보완한다.

    사용자가 수정했을 수 있는 다른 열은 절대 덮어쓰지 않는다.
    """
    existing_summary = _cell(existing_row, 8)
    if existing_summary:
        print(
            f"[ISSUE REPORT][SKIP] {report.tc_id} -> {report.jira_key} "
            "summary already exists"
        )
        return False

    summary = (report.issue_summary or "").strip()
    if not summary:
        print(
            f"[ISSUE REPORT][SKIP] {report.tc_id} -> {report.jira_key} "
            "generated summary is empty"
        )
        return False

    range_name = f"'{SHEET_NAME}'!I{sheet_row}"
    updated = update_value(range_name, summary)
    if updated != 1:
        raise RuntimeError(
            f"이슈 요약 백필 실패: {report.tc_id} {range_name} updatedCells={updated}"
        )

    print(f"[ISSUE REPORT][BACKFILL] {report.tc_id} {range_name} -> summary updated")
    return True


def ensure_issue_report_row(report: IssueReportRow) -> bool:
    """이슈 리포트 신규 행 추가 또는 기존 행의 빈 이슈 요약을 보완한다.

    동작:
        - 동일 Jira key 없음: 신규 행 추가
        - 동일 Jira key 있음 + I열 비어 있음: I열만 백필
        - 동일 Jira key 있음 + I열 값 있음: SKIP

    Returns:
        True: 신규 행 추가 또는 이슈 요약 백필
        False: 변경할 내용이 없어 SKIP
    """
    rows = read_values(REPORT_RANGE)

    existing = _find_jira_key_row(rows, report.jira_key)
    if existing is not None:
        sheet_row, existing_row = existing
        return _backfill_issue_summary(
            report=report,
            sheet_row=sheet_row,
            existing_row=existing_row,
        )

    no = _next_no(rows)
    values = report.values(no)
    updated = append_values(REPORT_RANGE, [values])
    if updated != len(values):
        raise RuntimeError(
            "이슈 리포트 기록 실패: "
            f"{report.tc_id} updatedCells={updated}, expected={len(values)}"
        )

    print(f"[ISSUE REPORT][ADDED] NO={no} {report.tc_id} -> {report.jira_key}")
    return True
