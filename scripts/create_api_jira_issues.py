"""API 자동화 Fail TC를 Jira 이슈 후보로 만들고 선택적으로 생성한다."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google_sheets_client import read_values, update_value
from inspect_allure_results import (
    STATUS_ORDER,
    aggregate_by_mapping_key,
    load_attempts,
)
from jira_client import JiraClient, adf_from_sections
from jira_issue_fields import area_from_api_tc_id, build_qa_issue_fields
from issue_report import (
    IssueReportRow,
    build_issue_summary,
    ensure_issue_report_row,
)
from tc_mapping import normalize_file_name, normalize_function_name


API_TC_RANGE = "'API 테스트'!B12:O"
HEADER_ROW = 12

# B:O 범위를 B=0으로 계산
IDX_TC_ID = 0
IDX_CATEGORY_1 = 2
IDX_CATEGORY_2 = 3
IDX_CATEGORY_3 = 4
IDX_PRECONDITION = 5
IDX_STEPS = 6
IDX_EXPECTED = 7
IDX_RESULT = 8
IDX_AUTOMATION = 9
IDX_COMMENT = 10
IDX_FILE = 11
IDX_FUNCTION = 12
IDX_JIRA_LINK = 13

MAX_FAILURE_MESSAGE = 3500
MAX_TRACE = 5000
MAX_SUMMARY = 250


@dataclass(frozen=True)
class ApiTC:
    tc_id: str
    sheet_row: int
    priority: str
    title: str
    category_1: str
    category_2: str
    category_3: str
    precondition: str
    steps: str
    expected: str
    current_result: str
    comment: str
    file_name: str
    function_name: str
    jira_link: str

    @property
    def key(self) -> tuple[str, str]:
        return self.file_name, self.function_name


@dataclass(frozen=True)
class JiraCandidate:
    tc: ApiTC
    summary: str
    failure_message: str
    trace: str
    build_url: str
    allure_url: str


def _cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index] or "").strip()


def _mask_sensitive_text(value: str) -> str:
    text = value or ""
    text = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,'\"}]+",
        r"\1<masked>",
        text,
    )
    text = re.sub(
        r"(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]+",
        r"\1<masked>",
        text,
    )
    text = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "<masked-email>",
        text,
    )
    text = re.sub(
        r"(?i)(sessionkey|api[_-]?token|access[_-]?token|password)"
        r"(\s*[:=]\s*)([^\s,'\"}]+)",
        r"\1\2<masked>",
        text,
    )
    return text


def _clip(value: str, limit: int) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n... <truncated>"


def _pick_title(row: list[str], tc_id: str) -> tuple[str, str, str, str]:
    category_1 = _cell(row, IDX_CATEGORY_1)
    category_2 = _cell(row, IDX_CATEGORY_2)
    category_3 = _cell(row, IDX_CATEGORY_3)
    title = category_3 or category_2 or category_1 or tc_id
    return title, category_1, category_2, category_3


def load_api_tcs() -> list[ApiTC]:
    rows = read_values(API_TC_RANGE)
    tcs: list[ApiTC] = []

    for offset, row in enumerate(rows[1:], start=1):
        sheet_row = HEADER_ROW + offset
        tc_id = _cell(row, IDX_TC_ID)
        automation = _cell(row, IDX_AUTOMATION)
        file_name = normalize_file_name(_cell(row, IDX_FILE))
        function_name = normalize_function_name(_cell(row, IDX_FUNCTION))

        if automation != "자동화" or not tc_id or not file_name or not function_name:
            continue

        title, category_1, category_2, category_3 = _pick_title(row, tc_id)
        tcs.append(ApiTC(
            tc_id=tc_id,
            sheet_row=sheet_row,
            priority=_cell(row, 1),
            title=title,
            category_1=category_1,
            category_2=category_2,
            category_3=category_3,
            precondition=_cell(row, IDX_PRECONDITION),
            steps=_cell(row, IDX_STEPS),
            expected=_cell(row, IDX_EXPECTED),
            current_result=_cell(row, IDX_RESULT),
            comment=_cell(row, IDX_COMMENT),
            file_name=file_name,
            function_name=function_name,
            jira_link=_cell(row, IDX_JIRA_LINK),
        ))

    return tcs


def _build_candidate(tc: ApiTC, aggregate: dict[str, Any]) -> JiraCandidate:
    failed_attempts = [
        item for item in aggregate["attempts"]
        if item.status in {"failed", "broken"}
    ]
    representative = max(
        failed_attempts or aggregate["attempts"],
        key=lambda item: (
            STATUS_ORDER.get(item.status, 0), item.stop, item.start
        ),
    )

    failure_message = _clip(
        _mask_sensitive_text(representative.message), MAX_FAILURE_MESSAGE
    )
    trace = _clip(_mask_sensitive_text(representative.trace), MAX_TRACE)

    build_url = os.getenv("BUILD_URL", "").strip()
    allure_url = (
        os.getenv("ALLURE_REPORT_URL", "").strip()
        or (f"{build_url}allure/" if build_url else "")
    )
    summary = _clip(f"[API][{tc.tc_id}] {tc.title} 실패", MAX_SUMMARY)

    return JiraCandidate(
        tc=tc,
        summary=summary,
        failure_message=failure_message or "실패 메시지 없음",
        trace=trace or "trace 없음",
        build_url=build_url or "Jenkins 외부 실행 / BUILD_URL 없음",
        allure_url=allure_url or "Allure URL 없음",
    )


def build_candidates(results_dir: Path) -> tuple[
    list[JiraCandidate],
    list[tuple[str, str]],
    dict[tuple[str, str], list[ApiTC]],
    list[ApiTC],
]:
    attempts = load_attempts(results_dir)
    # raw attempt 전체를 집계해야 FAIL -> rerun PASS 이력을 보존할 수 있다.
    aggregated = aggregate_by_mapping_key(attempts)

    tcs = load_api_tcs()
    grouped: dict[tuple[str, str], list[ApiTC]] = defaultdict(list)
    for tc in tcs:
        grouped[tc.key].append(tc)

    duplicate_keys = {
        key: values for key, values in grouped.items() if len(values) > 1
    }

    candidates: list[JiraCandidate] = []
    failed_unmapped: list[tuple[str, str]] = []
    result_mismatch: list[ApiTC] = []

    for key, aggregate in sorted(aggregated.items()):
        if aggregate["status"] != "failed":
            continue

        mapped = grouped.get(key, [])
        if not mapped:
            failed_unmapped.append(key)
            continue
        if key in duplicate_keys:
            continue

        tc = mapped[0]
        # Allure Fail과 Sheet 결과가 모두 Fail일 때만 실제 Jira 후보로 인정한다.
        if tc.current_result != "Fail":
            result_mismatch.append(tc)
            continue

        candidates.append(_build_candidate(tc, aggregate))

    return candidates, failed_unmapped, duplicate_keys, result_mismatch


def _sections(candidate: JiraCandidate) -> list[tuple[str, str]]:
    tc = candidate.tc
    tc_info = (
        f"TC ID: {tc.tc_id}\n"
        f"테스트명: {tc.title}\n"
        f"파일명: {tc.file_name}\n"
        f"함수명: {tc.function_name}"
    )
    automation_info = (
        f"Jenkins: {candidate.build_url}\n"
        f"Allure: {candidate.allure_url}"
    )
    return [
        ("TC 정보", tc_info),
        ("사전 조건", tc.precondition or "-"),
        ("테스트 절차", tc.steps or "-"),
        ("기대 결과", tc.expected or "-"),
        ("실제 실패 결과", candidate.failure_message),
        ("기술 상세 / Stack trace", candidate.trace),
        ("자동화 정보", automation_info),
    ]


def _print_candidate(index: int, candidate: JiraCandidate) -> None:
    print("\n" + "=" * 80)
    print(f"[JIRA CANDIDATE {index}]")
    print("=" * 80)
    print(f"Sheet row : {candidate.tc.sheet_row}")
    print(f"TC ID     : {candidate.tc.tc_id}")
    print(f"Summary   : {candidate.summary}")
    print(f"File      : {candidate.tc.file_name}")
    print(f"Function  : {candidate.tc.function_name}")
    for heading, body in _sections(candidate)[1:]:
        print(f"\n[{heading}]")
        print(body)



def _write_jira_link(tc: ApiTC, issue_url: str) -> None:
    """생성/재사용한 Jira 이슈 URL을 해당 TC의 O열에 기록한다."""
    if tc.jira_link == issue_url:
        print(f"[SHEET][SKIP] {tc.tc_id} O{tc.sheet_row} already up-to-date")
        return

    range_name = f"'API 테스트'!O{tc.sheet_row}"
    updated_cells = update_value(range_name, issue_url)
    if updated_cells != 1:
        raise RuntimeError(
            f"Jira 링크 Sheet 기록 실패: {tc.tc_id} {range_name} "
            f"updatedCells={updated_cells}"
        )
    print(f"[SHEET][UPDATED] {tc.tc_id} O{tc.sheet_row} -> {issue_url}")


def _write_issue_report(
    candidate: JiraCandidate,
    issue_key: str,
    issue_url: str,
) -> None:
    tc = candidate.tc
    ensure_issue_report_row(
        IssueReportRow(
            tc_id=tc.tc_id,
            location=tc.category_1 or tc.category_2 or "-",
            issue_name=candidate.summary,
            test_type="API",
            precondition=tc.precondition or "-",
            reproduction_steps=tc.steps or "-",
            expected=tc.expected or "-",
            issue_summary=build_issue_summary(
                title=candidate.summary,
                expected=tc.expected or "-",
                actual=candidate.failure_message,
            ),
            actual=candidate.failure_message,
            log_01=candidate.trace,
            log_02=f"Jenkins: {candidate.build_url}",
            log_03=f"Allure: {candidate.allure_url}",
            jira_key=issue_key,
            jira_link=issue_url,
        )
    )

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results-dir",
        default="allure-results/api",
        help="Allure raw result directory",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 Jira 이슈를 생성한다. 기본값은 Dry-run.",
    )
    parser.add_argument(
        "--tc-id",
        help="특정 TC ID만 대상으로 한다. 실제 생성 POC에 권장.",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"[ERROR] Allure results directory not found: {results_dir}")
        return 1

    candidates, failed_unmapped, duplicate_keys, result_mismatch = (
        build_candidates(results_dir)
    )

    if args.tc_id:
        candidates = [c for c in candidates if c.tc.tc_id == args.tc_id]

    mode = "APPLY" if args.apply else "DRY RUN"
    print("=" * 80)
    print(f"[API Jira Issue Candidate - {mode}]")
    print("=" * 80)
    print(f"Mapped Fail Jira candidates : {len(candidates)}")
    print(f"Failed but not in TC Sheet  : {len(failed_unmapped)}")
    print(f"Sheet result mismatch       : {len(result_mismatch)}")
    print(f"Duplicate mapping keys      : {len(duplicate_keys)}")
    print(f"Jira write                  : {'ENABLED' if args.apply else 'DISABLED'}")

    for index, candidate in enumerate(candidates, start=1):
        _print_candidate(index, candidate)

    if failed_unmapped:
        print("\n[SKIP] Fail이지만 Google Sheet TC 매핑이 없는 테스트")
        for file_name, function_name in failed_unmapped:
            print(f"  - {file_name}::{function_name}")

    if result_mismatch:
        print("\n[SKIP] Allure=failed 이지만 Sheet 테스트 결과가 Fail이 아닌 TC")
        for tc in result_mismatch:
            print(
                f"  - {tc.tc_id} row {tc.sheet_row}: "
                f"Sheet result={tc.current_result!r}"
            )

    if duplicate_keys:
        print("\n[SKIP] 중복 파일명+함수명 매핑")
        for (file_name, function_name), items in sorted(duplicate_keys.items()):
            ids = ", ".join(
                f"{item.tc_id}(row {item.sheet_row})" for item in items
            )
            print(f"  - {file_name}::{function_name} -> {ids}")

    if not args.apply:
        print("\n" + "=" * 80)
        print("[DRY RUN] Jira issue was not created.")
        print("=" * 80)
        return 0

    if not candidates:
        print("\n[APPLY] 생성할 Jira 이슈가 없습니다.")
        return 0

    client = JiraClient.from_env()
    issue_type = client.find_bug_issue_type()
    issue_type_id = str(issue_type.get("id") or "").strip()
    issue_type_name = str(issue_type.get("name") or "").strip()
    if not issue_type_id:
        raise RuntimeError(f"Jira issue type ID가 없습니다: {issue_type}")
    print(f"[JIRA] Selected issue type: {issue_type_name} (id={issue_type_id})")

    created = 0
    reused = 0

    for candidate in candidates:
        existing = client.search_open_issue_by_tc_id(
            candidate.tc.tc_id,
            test_type="API",
        )
        if existing:
            issue = existing[0]
            issue_key = str(issue.get("key") or "").strip()
            issue_url = client.issue_url(issue_key)
            print(
                f"[SKIP][EXISTING] {candidate.tc.tc_id} -> "
                f"{issue_key} {issue_url}"
            )
            _write_jira_link(candidate.tc, issue_url)
            _write_issue_report(candidate, issue_key, issue_url)
            reused += 1
            continue

        extra_fields = build_qa_issue_fields(
            client,
            issue_type_id=issue_type_id,
            area=area_from_api_tc_id(candidate.tc.tc_id),
            priority=candidate.tc.priority,
            test_type="API",
        )

        response = client.create_issue(
            summary=candidate.summary,
            description_adf=adf_from_sections(_sections(candidate)),
            issue_type_id=issue_type_id,
            extra_fields=extra_fields,
        )
        issue_key = str(response.get("key") or "").strip()
        if not issue_key:
            raise RuntimeError(
                f"Jira 생성 응답에 issue key가 없습니다: {response}"
            )

        issue_url = client.issue_url(issue_key)
        created += 1
        print(
            f"[CREATED] {candidate.tc.tc_id} -> "
            f"{issue_key} {issue_url}"
        )
        _write_jira_link(candidate.tc, issue_url)
        _write_issue_report(candidate, issue_key, issue_url)

    print("\n" + "=" * 80)
    print("[APPLY] Jira issue processing completed")
    print(f"Created       : {created}")
    print(f"Existing skip : {reused}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("=" * 80)
        print("[ERROR] API Jira issue processing failed")
        print("=" * 80)
        print(str(exc))
        print("=" * 80)
        sys.exit(1)
