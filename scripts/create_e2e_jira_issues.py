"""E2E 통합 시나리오 Fail TC를 Jira 버그 후보로 만들고 선택적으로 생성한다."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from e2e_tc_results import load_final_tc_results, validate_expected_coverage
from google_sheets_client import read_values, update_value
from jira_client import JiraClient, adf_from_sections
from jira_issue_fields import area_from_e2e_linked_tc, build_qa_issue_fields
from issue_report import (
    IssueReportRow,
    build_issue_summary,
    ensure_issue_report_row,
)


SHEET_NAME = "전체 기능(E2E 통합)"
SHEET_RANGE = f"'{SHEET_NAME}'!A4:I105"
START_ROW = 4
MAX_FAILURE_MESSAGE = 3500
MAX_TRACE = 5000
MAX_SUMMARY = 250


@dataclass(frozen=True)
class E2ETC:
    tc_id: str
    step: int
    sheet_row: int
    priority: str
    linked_tc: str
    section: str
    account: str
    action: str
    expected: str
    current_result: str
    note: str
    jira_link: str


@dataclass(frozen=True)
class JiraCandidate:
    tc: E2ETC
    summary: str
    failure_message: str
    trace: str
    build_url: str
    allure_url: str
    rerun_recovered: bool
    retry_sequence: str


def _cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index] or "").strip()


def _mask_sensitive_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,'\"}]+", r"\1<masked>", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<masked-email>", text)
    text = re.sub(
        r"(?i)(sessionkey|api[_-]?token|access[_-]?token|password)(\s*[:=]\s*)([^\s,'\"}]+)",
        r"\1\2<masked>",
        text,
    )
    return text


def _clip(value: str, limit: int) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n... <truncated>"


def load_e2e_sheet() -> tuple[str, list[E2ETC]]:
    rows = read_values(SHEET_RANGE)
    if len(rows) < 5:
        raise RuntimeError(f"E2E Sheet 구조를 읽지 못했습니다: {SHEET_RANGE}")

    # A4:H4 = 시나리오 메타. D4가 우선순위 값이다.
    priority = _cell(rows[0], 3) or "상"
    tcs: list[E2ETC] = []

    # A7:H7가 단계 헤더이고 A8부터 step 1이다.
    for index, row in enumerate(rows[4:], start=8):
        step_raw = _cell(row, 0)
        if not step_raw.isdigit():
            continue
        step = int(step_raw)
        tcs.append(
            E2ETC(
                tc_id=f"E2E-ALL-{step:03d}",
                step=step,
                sheet_row=index,
                priority=priority,
                linked_tc=_cell(row, 1),
                section=_cell(row, 2),
                account=_cell(row, 3),
                action=_cell(row, 4),
                expected=_cell(row, 5),
                current_result=_cell(row, 6),
                note=_cell(row, 7),
                jira_link=_cell(row, 8),
            )
        )
    return priority, tcs


def _build_candidate(tc: E2ETC, result: dict[str, Any]) -> JiraCandidate:
    title = str(result.get("title") or "").strip() or tc.action
    failure_message = _clip(
        _mask_sensitive_text(str(result.get("error") or "실패 메시지 없음")),
        MAX_FAILURE_MESSAGE,
    )
    trace = _clip(
        _mask_sensitive_text(str(result.get("traceback") or "trace 없음")),
        MAX_TRACE,
    )
    build_url = os.getenv("BUILD_URL", "").strip()
    allure_url = os.getenv("ALLURE_REPORT_URL", "").strip() or (
        f"{build_url}allure/" if build_url else ""
    )
    short_title = title
    short_title = re.sub(r"^\[단계\s*0*\d+\]\s*", "", short_title)
    rerun_recovered = bool(result.get("rerun_recovered"))
    rerun_tag = "[RERUN PASS]" if rerun_recovered else ""
    summary = _clip(
        f"[E2E][{tc.tc_id}]{rerun_tag} {short_title} 실패",
        MAX_SUMMARY,
    )
    return JiraCandidate(
        tc=tc,
        summary=summary,
        failure_message=failure_message,
        trace=trace,
        build_url=build_url or "Jenkins 외부 실행 / BUILD_URL 없음",
        allure_url=allure_url or "Allure URL 없음",
        rerun_recovered=bool(result.get("rerun_recovered")),
        retry_sequence=str(result.get("retry_sequence") or ""),
    )


def build_candidates(result_file: Path) -> tuple[list[JiraCandidate], list[E2ETC]]:
    final = load_final_tc_results(result_file)
    validate_expected_coverage(final)
    _, tcs = load_e2e_sheet()
    by_id = {tc.tc_id: tc for tc in tcs}

    candidates: list[JiraCandidate] = []
    sheet_mismatch: list[E2ETC] = []
    for tc_id, result in sorted(final.items()):
        if str(result.get("status") or "").strip().upper() != "FAIL":
            continue
        tc = by_id.get(tc_id)
        if tc is None:
            continue
        if tc.current_result != "Fail":
            sheet_mismatch.append(tc)
            continue
        candidates.append(_build_candidate(tc, result))
    return candidates, sheet_mismatch


def _sections(candidate: JiraCandidate) -> list[tuple[str, str]]:
    tc = candidate.tc
    tc_info = (
        f"TC ID: {tc.tc_id}\n"
        f"단계: {tc.step}\n"
        f"연계 TC: {tc.linked_tc}\n"
        f"구간: {tc.section}\n"
        f"계정: {tc.account}"
    )
    rerun_info = (
        f"Rerun recovered: {candidate.rerun_recovered}\n"
        f"Retry sequence: {candidate.retry_sequence or '-'}"
    )
    return [
        ("TC 정보", tc_info),
        ("테스트 절차", tc.action or "-"),
        ("기대 결과", tc.expected or "-"),
        ("실제 실패 결과", candidate.failure_message),
        ("기술 상세 / Stack trace", candidate.trace),
        ("Rerun 정보", rerun_info),
        (
            "자동화 정보",
            f"Jenkins: {candidate.build_url}\nAllure: {candidate.allure_url}",
        ),
    ]


def _write_jira_link(tc: E2ETC, issue_url: str) -> None:
    if tc.jira_link == issue_url:
        print(f"[SHEET][SKIP] {tc.tc_id} I{tc.sheet_row} already up-to-date")
        return
    range_name = f"'{SHEET_NAME}'!I{tc.sheet_row}"
    updated = update_value(range_name, issue_url)
    if updated != 1:
        raise RuntimeError(
            f"E2E Jira 링크 기록 실패: {tc.tc_id} {range_name} updatedCells={updated}"
        )
    print(f"[SHEET][UPDATED] {tc.tc_id} I{tc.sheet_row} -> {issue_url}")



def _write_issue_report(
    candidate: JiraCandidate,
    issue_key: str,
    issue_url: str,
) -> None:
    tc = candidate.tc
    ensure_issue_report_row(
        IssueReportRow(
            tc_id=tc.tc_id,
            location=tc.section or tc.linked_tc or "-",
            issue_name=candidate.summary,
            test_type="E2E",
            precondition=f"계정: {tc.account}" if tc.account else "-",
            reproduction_steps=tc.action or "-",
            expected=tc.expected or "-",
            issue_summary=build_issue_summary(
                title=candidate.summary,
                expected=tc.expected or "-",
                actual=candidate.failure_message,
            ),
            actual=candidate.failure_message,
            # E2E 스크린샷 Jira 첨부 연동 전까지는 trace/Jenkins/Allure를 기록한다.
            # 스크린샷 첨부 기능이 연결되면 log_01에 첨부 파일명을 기록한다.
            log_01=candidate.trace,
            log_02=(
                f"Rerun recovered: {candidate.rerun_recovered}\n"
                f"Retry sequence: {candidate.retry_sequence or '-'}"
            ),
            log_03=(
                f"Jenkins: {candidate.build_url}\n"
                f"Allure: {candidate.allure_url}"
            ),
            jira_key=issue_key,
            jira_link=issue_url,
        )
    )

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result-file",
        default="artifacts/tc-results/tc_results.jsonl",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--tc-id", help="단일 E2E TC POC용. 예: E2E-ALL-001")
    args = parser.parse_args()

    candidates, mismatch = build_candidates(Path(args.result_file))
    if args.tc_id:
        candidates = [c for c in candidates if c.tc.tc_id == args.tc_id]

    mode = "APPLY" if args.apply else "DRY RUN"
    print("=" * 80)
    print(f"[E2E Jira Issue Candidate - {mode}]")
    print("=" * 80)
    print(f"Mapped Fail Jira candidates : {len(candidates)}")
    print(f"Sheet result mismatch       : {len(mismatch)}")
    print(f"Jira write                  : {'ENABLED' if args.apply else 'DISABLED'}")

    for index, candidate in enumerate(candidates, start=1):
        print("\n" + "=" * 80)
        print(f"[JIRA CANDIDATE {index}]")
        print(f"TC ID     : {candidate.tc.tc_id}")
        print(f"Sheet row : {candidate.tc.sheet_row}")
        print(f"Summary   : {candidate.summary}")
        print(f"Linked TC : {candidate.tc.linked_tc}")
        print(f"Result    : {candidate.failure_message}")

    if not args.apply:
        print("\n[DRY RUN] Jira issue was not created.")
        return 0
    if not candidates:
        print("\n[APPLY] 생성할 Jira 이슈가 없습니다.")
        return 0

    client = JiraClient.from_env()
    issue_type = client.find_bug_issue_type()
    issue_type_id = str(issue_type.get("id") or "").strip()
    if not issue_type_id:
        raise RuntimeError(f"Jira Bug issue type ID가 없습니다: {issue_type}")

    created = 0
    reused = 0
    for candidate in candidates:
        tc = candidate.tc
        existing = client.search_open_issue_by_tc_id(tc.tc_id, test_type="E2E")
        if existing:
            issue_key = str(existing[0].get("key") or "").strip()
            issue_url = client.issue_url(issue_key)
            print(f"[SKIP][EXISTING] {tc.tc_id} -> {issue_key} {issue_url}")
            _write_jira_link(tc, issue_url)
            _write_issue_report(candidate, issue_key, issue_url)
            reused += 1
            continue

        area = area_from_e2e_linked_tc(tc.linked_tc)
        extra_fields = build_qa_issue_fields(
            client,
            issue_type_id=issue_type_id,
            area=area,
            priority=tc.priority,
            test_type="E2E",
        )
        response = client.create_issue(
            summary=candidate.summary,
            description_adf=adf_from_sections(_sections(candidate)),
            issue_type_id=issue_type_id,
            extra_fields=extra_fields,
        )
        issue_key = str(response.get("key") or "").strip()
        if not issue_key:
            raise RuntimeError(f"Jira 생성 응답에 issue key가 없습니다: {response}")
        issue_url = client.issue_url(issue_key)
        print(f"[CREATED] {tc.tc_id} -> {issue_key} {issue_url}")
        _write_jira_link(tc, issue_url)
        _write_issue_report(candidate, issue_key, issue_url)
        created += 1

    print("\n" + "=" * 80)
    print("[APPLY] E2E Jira issue processing completed")
    print(f"Created       : {created}")
    print(f"Existing skip : {reused}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("=" * 80)
        print("[ERROR] E2E Jira issue processing failed")
        print("=" * 80)
        print(str(exc))
        print("=" * 80)
        sys.exit(1)
