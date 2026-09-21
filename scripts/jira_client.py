"""Jira Cloud REST API 공통 클라이언트."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class JiraConfigError(RuntimeError):
    """Jira 환경 설정 오류."""


class JiraApiError(RuntimeError):
    """Jira REST API 호출 오류."""


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise JiraConfigError(f"{name} 환경변수가 설정되지 않았습니다.")
    return value


def _basic_auth_header(email: str, api_token: str) -> str:
    raw = f"{email}:{api_token}".encode("utf-8")
    return f"Basic {base64.b64encode(raw).decode('ascii')}"


def _request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None
    request_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read().decode(charset)
            return json.loads(raw) if raw.strip() else {}
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise JiraApiError(
            f"Jira API HTTP {exc.code}\nURL: {url}\n응답: {error_body[:2000]}"
        ) from exc
    except URLError as exc:
        raise JiraApiError(
            f"Jira API 연결 실패\nURL: {url}\n원인: {exc.reason}"
        ) from exc


@dataclass(frozen=True)
class JiraClient:
    site_url: str
    api_base_url: str
    project_key: str
    headers: dict[str, str]

    @classmethod
    def from_env(cls) -> "JiraClient":
        site_url = _required_env("JIRA_BASE_URL").rstrip("/")
        email = _required_env("JIRA_USER_EMAIL")
        api_token = _required_env("JIRA_API_TOKEN")
        project_key = _required_env("JIRA_PROJECT_KEY")

        tenant = _request_json(f"{site_url}/_edge/tenant_info")
        cloud_id = str((tenant or {}).get("cloudId") or "").strip()
        if not cloud_id:
            raise JiraApiError(f"Jira cloudId 조회 실패: {tenant}")

        return cls(
            site_url=site_url,
            api_base_url=f"https://api.atlassian.com/ex/jira/{cloud_id}",
            project_key=project_key,
            headers={
                "Accept": "application/json",
                "Authorization": _basic_auth_header(email, api_token),
            },
        )

    def get_issue_types(self) -> list[dict[str, Any]]:
        project = quote(self.project_key, safe="")
        data = _request_json(
            f"{self.api_base_url}/rest/api/3/issue/createmeta/{project}/issuetypes",
            headers=self.headers,
        )
        return list((data or {}).get("issueTypes") or [])

    def find_bug_issue_type(self) -> dict[str, Any]:
        issue_types = self.get_issue_types()
        for item in issue_types:
            if str(item.get("name") or "").strip().casefold() in {"bug", "버그"}:
                return item
        names = [str(item.get("name") or "") for item in issue_types]
        raise JiraApiError(
            f"Bug/버그 이슈 유형을 찾지 못했습니다. 생성 가능한 유형: {names}"
        )

    def get_create_fields(self, issue_type_id: str) -> list[dict[str, Any]]:
        project = quote(self.project_key, safe="")
        issue_type = quote(issue_type_id, safe="")
        start_at = 0
        fields: list[dict[str, Any]] = []
        while True:
            query = urlencode({"startAt": start_at, "maxResults": 100})
            url = (
                f"{self.api_base_url}/rest/api/3/issue/createmeta/"
                f"{project}/issuetypes/{issue_type}?{query}"
            )
            data = _request_json(url, headers=self.headers) or {}
            page = list(data.get("fields") or [])
            fields.extend(page)
            total = int(data.get("total") or len(fields))
            if not page or len(fields) >= total:
                break
            start_at += len(page)
        return fields

    def find_assignable_user(self, display_name: str) -> dict[str, Any]:
        query = urlencode(
            {
                "project": self.project_key,
                "query": display_name,
                "maxResults": 50,
            }
        )
        url = f"{self.api_base_url}/rest/api/3/user/assignable/search?{query}"
        users = _request_json(url, headers=self.headers)
        if not isinstance(users, list):
            raise JiraApiError(f"Jira 담당자 조회 응답 형식이 예상과 다릅니다: {users}")

        exact = [
            user
            for user in users
            if str(user.get("displayName") or "").strip() == display_name
            and user.get("active", True)
        ]
        if len(exact) == 1 and exact[0].get("accountId"):
            return exact[0]
        if not exact:
            found = [str(user.get("displayName") or "") for user in users]
            raise JiraApiError(
                f"프로젝트에 할당 가능한 담당자 '{display_name}'을 찾지 못했습니다. "
                f"검색 결과: {found}"
            )
        raise JiraApiError(
            f"담당자 '{display_name}'이 여러 계정과 정확히 일치합니다. accountId를 확인하세요."
        )

    def search_open_issue_by_tc_id(
        self,
        tc_id: str,
        *,
        test_type: str = "API",
    ) -> list[dict[str, Any]]:
        escaped = tc_id.replace('"', '\\"')
        jql = (
            f'project = "{self.project_key}" '
            f"AND statusCategory != Done "
            f'AND summary ~ "{escaped}"'
        )
        data = (
            _request_json(
                f"{self.api_base_url}/rest/api/3/search/jql",
                method="POST",
                headers=self.headers,
                payload={"jql": jql, "maxResults": 20, "fields": ["summary", "status"]},
            )
            or {}
        )
        token = f"[{test_type}][{tc_id}]"
        return [
            issue
            for issue in list(data.get("issues") or [])
            if token in str((issue.get("fields") or {}).get("summary") or "")
        ]

    def create_issue(
        self,
        *,
        summary: str,
        description_adf: dict[str, Any],
        issue_type_id: str,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": self.project_key},
            "issuetype": {"id": issue_type_id},
            "summary": summary,
            "description": description_adf,
        }
        fields.update(extra_fields or {})
        return _request_json(
            f"{self.api_base_url}/rest/api/3/issue",
            method="POST",
            headers=self.headers,
            payload={"fields": fields},
        )

    def issue_url(self, issue_key: str) -> str:
        return f"{self.site_url}/browse/{issue_key}"


def adf_from_sections(sections: list[tuple[str, str]]) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for heading, body in sections:
        content.append(
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": heading}],
            }
        )
        for line in (body or "-").splitlines() or ["-"]:
            content.append(
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line or " "}],
                }
            )
    return {"type": "doc", "version": 1, "content": content}
