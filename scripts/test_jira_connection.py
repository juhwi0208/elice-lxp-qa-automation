"""Jenkins에서 Jira Cloud API 연결 상태를 검증한다."""

from __future__ import annotations

import base64
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _required_env(name: str) -> str:
    """필수 환경변수를 읽고 없으면 즉시 실패한다."""
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(f"필수 환경변수가 없습니다: {name}")

    return value


def _read_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict:
    """GET 요청 후 JSON 응답을 반환한다."""
    request = Request(
        url,
        headers=headers or {},
        method="GET",
    )

    try:
        with urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset)

            return json.loads(payload)

    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")

        raise RuntimeError(
            f"HTTP {exc.code} 응답이 반환되었습니다.\nURL: {url}\n응답: {body[:1000]}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"Jira API 연결에 실패했습니다.\nURL: {url}\n원인: {exc.reason}"
        ) from exc


def _basic_auth_header(
    email: str,
    api_token: str,
) -> str:
    """Atlassian email + API token Basic 인증 헤더를 만든다."""
    credentials = f"{email}:{api_token}".encode("utf-8")
    encoded = base64.b64encode(credentials).decode("ascii")

    return f"Basic {encoded}"


def main() -> int:
    jira_base_url = _required_env("JIRA_BASE_URL").rstrip("/")
    jira_user_email = _required_env("JIRA_USER_EMAIL")
    jira_api_token = _required_env("JIRA_API_TOKEN")
    jira_project_key = _required_env("JIRA_PROJECT_KEY")

    print("=" * 60)
    print("[Jira] Jira Cloud API connection test")
    print("=" * 60)

    # 1. Jira 사이트의 cloudId 확인
    tenant_info_url = f"{jira_base_url}/_edge/tenant_info"

    print("[1/3] Resolving Jira cloudId")

    tenant_info = _read_json(tenant_info_url)
    cloud_id = str(tenant_info.get("cloudId", "")).strip()

    if not cloud_id:
        raise RuntimeError(f"Jira cloudId를 확인하지 못했습니다. 응답: {tenant_info}")

    print("[OK] Jira cloudId resolved")

    # 2. Scoped API Token용 Atlassian API gateway 구성
    jira_api_base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"

    auth_header = _basic_auth_header(
        jira_user_email,
        jira_api_token,
    )

    headers = {
        "Accept": "application/json",
        "Authorization": auth_header,
    }

    # 3. TQA 프로젝트/스페이스 조회
    project_url = f"{jira_api_base_url}/rest/api/3/project/{jira_project_key}"

    print(
        f"[2/3] Validating Jira authentication and project access: {jira_project_key}"
    )

    project = _read_json(
        project_url,
        headers=headers,
    )

    actual_key = str(project.get("key", "")).strip()
    project_name = str(project.get("name", "")).strip()
    project_id = str(project.get("id", "")).strip()

    if actual_key != jira_project_key:
        raise RuntimeError(
            "조회된 Jira 프로젝트 키가 예상 값과 다릅니다. "
            f"expected={jira_project_key}, actual={actual_key}"
        )

    print("[OK] Jira API authentication succeeded")
    print("[OK] Jira project is accessible")

    print("[3/3] Connection summary")
    print(f"Site URL    : {jira_base_url}")
    print(f"Project Key : {actual_key}")
    print(f"Project Name: {project_name}")
    print(f"Project ID  : {project_id}")

    print("=" * 60)
    print("[OK] Jira connection validation completed")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())

    except Exception as exc:
        print("=" * 60)
        print("[ERROR] Jira connection validation failed")
        print("=" * 60)
        print(str(exc))
        print("=" * 60)

        sys.exit(1)
