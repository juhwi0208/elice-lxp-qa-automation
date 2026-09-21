"""Triple Q Jira 버그 공통 세부 필드 해석 규칙."""

from __future__ import annotations

import re
from typing import Any

from jira_client import JiraApiError, JiraClient


ASSIGNEE_BY_AREA = {
    "CL": "강승완",
    "CS": "이명종",
    "BO": "이주휘",
    "CH": "강승완",
}

FEATURE_BY_AREA = {
    "CL": "Course List",
    "CS": "Class Schedule",
    "BO": "Board",
    "CH": "Classroom Home",
}

# TC Sheet에서는 상/중/하만 사용한다.
# Jira 실제 Priority 옵션은 High/Medium/Low로 매핑한다.
PRIORITY_ALIASES = {
    "상": ("High",),
    "중": ("Medium",),
    "하": ("Low",),
}


def area_from_api_tc_id(tc_id: str) -> str:
    prefix = (tc_id or "").split("-", 1)[0].strip().upper()

    if prefix not in FEATURE_BY_AREA:
        raise JiraApiError(f"Jira 영역 매핑이 없는 API TC prefix입니다: {tc_id}")

    return prefix


def area_from_e2e_linked_tc(linked_tc: str) -> str:
    """E2E 시트의 연계 TC 문자열에서 Jira 기능 영역을 해석한다."""
    areas = {
        match.group(1)
        for match in re.finditer(r"(?<![A-Z0-9])(CL|CS|BO|CH)(?=[-_\s]|\d|$)", (linked_tc or "").upper())
    }
    if len(areas) != 1:
        raise JiraApiError(
            f"E2E 연계 TC에서 Jira 영역을 하나로 결정할 수 없습니다: {linked_tc!r}"
        )
    return areas.pop()


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def _find_field(
    create_fields: list[dict[str, Any]],
    *names: str,
) -> dict[str, Any]:
    wanted = {_norm(name) for name in names}

    for field in create_fields:
        if _norm(field.get("name")) in wanted or _norm(field.get("fieldId")) in wanted:
            return field

    available = [
        (
            str(item.get("name") or ""),
            str(item.get("fieldId") or ""),
        )
        for item in create_fields
    ]

    raise JiraApiError(
        f"Jira 생성 화면에서 필드를 찾지 못했습니다: {names}. "
        f"생성 가능한 필드: {available}"
    )


def _allowed_payload(
    field: dict[str, Any],
    aliases: tuple[str, ...],
) -> dict[str, str]:
    wanted = {_norm(value) for value in aliases}
    allowed = list(field.get("allowedValues") or [])

    for option in allowed:
        candidates = (
            option.get("name"),
            option.get("value"),
            option.get("displayName"),
        )

        if any(_norm(value) in wanted for value in candidates):
            option_id = str(option.get("id") or "").strip()

            if option_id:
                return {
                    "id": option_id,
                }

            option_value = str(option.get("value") or option.get("name") or "").strip()

            if option_value:
                return {
                    "value": option_value,
                }

    values = [
        str(item.get("name") or item.get("value") or item.get("displayName") or "")
        for item in allowed
    ]

    raise JiraApiError(
        f"Jira 필드 '{field.get('name')}'에서 "
        f"옵션 {aliases}을 찾지 못했습니다. "
        f"현재 옵션: {values}"
    )


def build_qa_issue_fields(
    client: JiraClient,
    *,
    issue_type_id: str,
    area: str,
    priority: str,
    test_type: str,
) -> dict[str, Any]:
    """Triple Q 자동화 버그의 구조화 필드를 Jira payload 형식으로 만든다."""

    if area not in FEATURE_BY_AREA:
        raise JiraApiError(f"지원하지 않는 Jira 영역입니다: {area}")

    create_fields = client.get_create_fields(issue_type_id)
    fields: dict[str, Any] = {}

    # --------------------------------------------------
    # 담당자
    # --------------------------------------------------
    assignee_name = ASSIGNEE_BY_AREA[area]
    assignee = client.find_assignable_user(assignee_name)

    account_id = str(assignee.get("accountId") or "").strip()

    if not account_id:
        raise JiraApiError(f"담당자 '{assignee_name}'의 accountId가 없습니다.")

    fields["assignee"] = {
        "accountId": account_id,
    }

    # --------------------------------------------------
    # 우선 순위
    # TC Sheet: 상/중/하
    # Jira: High/Medium/Low
    # --------------------------------------------------
    priority_field = _find_field(
        create_fields,
        "priority",
        "우선 순위",
        "Priority",
    )

    priority_aliases = PRIORITY_ALIASES.get(priority)

    if priority_aliases is None:
        raise JiraApiError(
            f"지원하지 않는 TC 우선순위입니다: {priority}. 사용 가능: 상, 중, 하"
        )

    fields["priority"] = _allowed_payload(
        priority_field,
        priority_aliases,
    )

    # --------------------------------------------------
    # 기능
    #
    # Jira UI의 '기능' 선택 필드.
    # native Jira Components가 아니다.
    # 반드시 실제 fieldId(customfield_xxx)를 사용한다.
    # --------------------------------------------------
    feature_field = _find_field(
        create_fields,
        "기능",
    )

    feature_field_id = str(feature_field.get("fieldId") or "").strip()

    if not feature_field_id:
        raise JiraApiError(f"Jira '기능' 필드에 fieldId가 없습니다: {feature_field}")

    if feature_field_id == "components":
        raise JiraApiError(
            "Jira '기능' 필드가 아직 system components 필드로 "
            "인식되고 있습니다. "
            "Jira 설정 저장 여부와 create metadata를 확인하세요."
        )

    fields[feature_field_id] = _allowed_payload(
        feature_field,
        (FEATURE_BY_AREA[area],),
    )

    # --------------------------------------------------
    # 테스트 유형
    # --------------------------------------------------
    test_type_field = _find_field(
        create_fields,
        "테스트 유형",
    )

    test_type_field_id = str(test_type_field.get("fieldId") or "").strip()

    if not test_type_field_id:
        raise JiraApiError("Jira '테스트 유형' 필드에 fieldId가 없습니다.")

    fields[test_type_field_id] = _allowed_payload(
        test_type_field,
        (test_type,),
    )

    # --------------------------------------------------
    # 이슈 발견 방식
    # --------------------------------------------------
    discovery_field = _find_field(
        create_fields,
        "이슈 발견 방식",
    )

    discovery_field_id = str(discovery_field.get("fieldId") or "").strip()

    if not discovery_field_id:
        raise JiraApiError("Jira '이슈 발견 방식' 필드에 fieldId가 없습니다.")

    fields[discovery_field_id] = _allowed_payload(
        discovery_field,
        ("자동화 테스트",),
    )

    # --------------------------------------------------
    # 재현 여부
    # --------------------------------------------------
    reproduction_field = _find_field(
        create_fields,
        "재현 여부",
    )

    reproduction_field_id = str(reproduction_field.get("fieldId") or "").strip()

    if not reproduction_field_id:
        raise JiraApiError("Jira '재현 여부' 필드에 fieldId가 없습니다.")

    fields[reproduction_field_id] = _allowed_payload(
        reproduction_field,
        ("재현 확인 필요",),
    )

    return fields
