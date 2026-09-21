"""Triple Q Jira 자동 생성 필드를 쓰기 없이 전체 사전 검증한다."""

from __future__ import annotations

import sys
from typing import Any

from jira_client import JiraApiError, JiraClient
from jira_issue_fields import (
    ASSIGNEE_BY_AREA,
    FEATURE_BY_AREA,
    PRIORITY_ALIASES,
    _find_field,
)


EXPECTED_TEST_TYPES = (
    "API",
    "E2E",
    "Performance",
)

EXPECTED_DISCOVERY_TYPES = (
    "자동화 테스트",
    "수동 테스트",
)

EXPECTED_REPRODUCIBILITY = (
    "재현됨",
    "재현 안 됨",
    "재현 확인 필요",
)


def _option_rows(
    field: dict[str, Any],
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    for option in list(field.get("allowedValues") or []):
        name = str(
            option.get("name") or option.get("value") or option.get("displayName") or ""
        ).strip()

        option_id = str(option.get("id") or "").strip()

        rows.append(
            (
                name,
                option_id,
            )
        )

    return rows


def _validate_options(
    *,
    label: str,
    field: dict[str, Any],
    expected: tuple[str, ...],
    errors: list[str],
) -> None:
    rows = _option_rows(field)
    actual_names = [name for name, _ in rows]

    print(f"\n[{label}]")
    print(f"fieldId : {field.get('fieldId')}")
    print(f"name    : {field.get('name')}")
    print(f"options : {rows}")

    for expected_name in expected:
        matches = [row for row in rows if row[0] == expected_name]

        if not matches:
            errors.append(
                f"[{label}] '{expected_name}' 옵션이 없습니다. "
                f"현재 옵션: {actual_names}"
            )
            continue

        if len(matches) > 1:
            errors.append(
                f"[{label}] '{expected_name}' 옵션이 중복되어 있습니다: {matches}"
            )
            continue

        print(f"[OK] {expected_name} (id={matches[0][1] or '-'})")


def main() -> int:
    client = JiraClient.from_env()

    errors: list[str] = []
    warnings: list[str] = []

    print("=" * 80)
    print("[Jira Issue Fields Full Validation - READ ONLY]")
    print("=" * 80)

    # --------------------------------------------------
    # 1. Issue Type / Create Metadata
    # --------------------------------------------------
    try:
        issue_type = client.find_bug_issue_type()

        issue_type_id = str(issue_type.get("id") or "").strip()

        if not issue_type_id:
            raise JiraApiError(f"Bug/버그 issue type ID가 없습니다: {issue_type}")

        print(f"[OK] Issue Type: {issue_type.get('name')} (id={issue_type_id})")

        create_fields = client.get_create_fields(issue_type_id)

    except Exception as exc:
        print(f"[ERROR] Issue Type/Create Metadata 조회 실패: {exc}")
        return 1

    # --------------------------------------------------
    # 2. Priority
    # --------------------------------------------------
    try:
        priority_field = _find_field(
            create_fields,
            "priority",
            "우선 순위",
            "Priority",
        )

        expected_priorities = tuple(aliases[0] for aliases in PRIORITY_ALIASES.values())

        _validate_options(
            label="우선 순위",
            field=priority_field,
            expected=expected_priorities,
            errors=errors,
        )

    except Exception as exc:
        errors.append(f"[우선 순위] {exc}")

    # --------------------------------------------------
    # 3. 기능
    #
    # Jira UI에서 만든 선택형 필드.
    # native components 필드가 아니어야 한다.
    # --------------------------------------------------
    try:
        feature_field = _find_field(
            create_fields,
            "기능",
        )

        feature_field_id = str(feature_field.get("fieldId") or "").strip()

        print("\n[기능]")
        print(f"fieldId : {feature_field_id}")
        print(f"name    : {feature_field.get('name')}")

        if not feature_field_id:
            errors.append("[기능] fieldId가 없습니다.")

        elif feature_field_id == "components":
            errors.append(
                "[기능] fieldId가 'components'로 조회됩니다. "
                "아직 Jira system Components 필드로 인식되는 상태입니다."
            )

        else:
            print(f"[OK] 기능 fieldId: {feature_field_id}")

        _validate_options(
            label="기능 옵션",
            field=feature_field,
            expected=tuple(FEATURE_BY_AREA.values()),
            errors=errors,
        )

    except Exception as exc:
        errors.append(f"[기능] {exc}")

    # --------------------------------------------------
    # 4. 테스트 유형
    # --------------------------------------------------
    try:
        test_type_field = _find_field(
            create_fields,
            "테스트 유형",
        )

        _validate_options(
            label="테스트 유형",
            field=test_type_field,
            expected=EXPECTED_TEST_TYPES,
            errors=errors,
        )

    except Exception as exc:
        errors.append(f"[테스트 유형] {exc}")

    # --------------------------------------------------
    # 5. 이슈 발견 방식
    # --------------------------------------------------
    try:
        discovery_field = _find_field(
            create_fields,
            "이슈 발견 방식",
        )

        _validate_options(
            label="이슈 발견 방식",
            field=discovery_field,
            expected=EXPECTED_DISCOVERY_TYPES,
            errors=errors,
        )

    except Exception as exc:
        errors.append(f"[이슈 발견 방식] {exc}")

    # --------------------------------------------------
    # 6. 재현 여부
    # --------------------------------------------------
    try:
        reproduction_field = _find_field(
            create_fields,
            "재현 여부",
        )

        _validate_options(
            label="재현 여부",
            field=reproduction_field,
            expected=EXPECTED_REPRODUCIBILITY,
            errors=errors,
        )

    except Exception as exc:
        errors.append(f"[재현 여부] {exc}")

    # --------------------------------------------------
    # 7. 담당자
    # --------------------------------------------------
    print("\n[담당자]")

    checked_names: set[str] = set()

    for assignee_name in ASSIGNEE_BY_AREA.values():
        if assignee_name in checked_names:
            continue

        checked_names.add(assignee_name)

        try:
            user = client.find_assignable_user(assignee_name)

            account_id = str(user.get("accountId") or "").strip()

            if not account_id:
                errors.append(f"[담당자] '{assignee_name}' accountId가 없습니다.")
                continue

            print(f"[OK] {assignee_name} (accountId={account_id})")

        except Exception as exc:
            errors.append(f"[담당자] '{assignee_name}' 자동 할당 불가: {exc}")

    # --------------------------------------------------
    # 최종 결과
    # --------------------------------------------------
    print("\n" + "=" * 80)
    print("[Validation Summary]")
    print("=" * 80)

    if warnings:
        print("\n[WARNINGS]")

        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("\n[ERRORS]")

        for error in errors:
            print(f"- {error}")

        print("\n" + "=" * 80)
        print(
            f"[FAIL] Jira 필드 사전검증 실패: "
            f"{len(errors)} error(s), "
            f"{len(warnings)} warning(s)"
        )
        print("=" * 80)

        return 1

    print(f"[OK] 전체 Jira 필드 사전검증 완료. error=0, warning={len(warnings)}")

    print("[OK] 실제 Jira 이슈는 생성하지 않았습니다.")

    print("=" * 80)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())

    except Exception as exc:
        print("=" * 80)
        print("[ERROR] Jira issue field validation failed")
        print("=" * 80)
        print(str(exc))
        print("=" * 80)

        sys.exit(1)
