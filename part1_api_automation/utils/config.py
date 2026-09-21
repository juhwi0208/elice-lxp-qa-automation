"""
config.py
.env 파일에서 환경변수를 읽어 QA 테스트 설정값을 제공한다.
실제 토큰·비밀번호는 이 파일에 기록하지 않는다.
"""

import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    """환경변수가 없으면 명시적으로 에러를 발생시킨다."""
    value = os.getenv(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"필수 환경변수 '{key}'가 설정되지 않았습니다. "
            ".env.example을 참고하여 .env 파일을 작성하세요."
        )
    return value


class Config:
    """QA 자동화에서 사용하는 설정 상수 모음."""

    # API 기본 주소 (예: https://api.example.com)
    BASE_URL: str = os.getenv("LXP_API_BASE_URL", "").rstrip("/")

    # 조직 식별자 (URL 경로 등에 사용)
    ORG_NAME_SHORT: str = os.getenv("LXP_ORG_NAME_SHORT", "")

    # QA 전용 클래스 식별값
    CLASSROOM_ID: str = os.getenv("LXP_CLASSROOM_ID", "")

    # 요청 타임아웃 (초)
    TIMEOUT: int = 10

    # 연속 호출 간 최소 대기 (초) — 서버 부하 방지
    CALL_INTERVAL: float = 0.3

    # 테스트 실행 전체에서 허용할 최대 실제 HTTP 호출 수
    MAX_REQUESTS: int = int(os.getenv("LXP_MAX_REQUESTS", "2000"))

    # 토큰을 전송해도 되는 QA 도메인. 환경변수로 변경할 수 없도록 고정한다.
    ALLOWED_HOST_SUFFIX: str = "dev.elicer.io"


def validate_base_url(value: str) -> str:
    """HTTPS 기반의 승인된 QA API 주소만 반환한다."""
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    suffix = Config.ALLOWED_HOST_SUFFIX

    if parsed.scheme != "https":
        raise EnvironmentError("LXP_API_BASE_URL은 HTTPS 주소여야 합니다.")
    if not host or not (host == suffix or host.endswith(f".{suffix}")):
        raise EnvironmentError(
            f"LXP_API_BASE_URL은 승인된 QA 도메인(*.{suffix})이어야 합니다."
        )
    if parsed.username or parsed.password:
        raise EnvironmentError("LXP_API_BASE_URL에는 사용자 정보를 포함할 수 없습니다.")
    if parsed.port not in (None, 443):
        raise EnvironmentError("LXP_API_BASE_URL은 기본 HTTPS 포트만 사용할 수 있습니다.")
    if parsed.params or parsed.query or parsed.fragment:
        raise EnvironmentError(
            "LXP_API_BASE_URL에는 파라미터, 쿼리 또는 프래그먼트를 포함할 수 없습니다."
        )

    return normalized


def require_base_url() -> str:
    """BASE_URL이 설정되어 있는지 확인 후 반환한다."""
    return validate_base_url(_require("LXP_API_BASE_URL"))


_SERVICE_BASE_URLS = {
    "account": (
        "LXP_ACCOUNT_API_BASE_URL",
        "https://dev-qatrack-account-api.dev.elicer.io",
    ),
    "classroom": (
        "LXP_CLASSROOM_API_BASE_URL",
        "https://dev-qatrack-classroom-api.dev.elicer.io",
    ),
    "course": (
        "LXP_COURSE_API_BASE_URL",
        "https://dev-qatrack-course-api.dev.elicer.io",
    ),
    "dashboard": (
        "LXP_DASHBOARD_API_BASE_URL",
        "https://dev-qatrack-dashboard-api.dev.elicer.io",
    ),
}


def require_service_base_url(service: str) -> str:
    """이름으로 지정한 학습 서비스의 승인된 QA URL을 반환한다."""
    normalized = service.strip().lower()
    if normalized not in _SERVICE_BASE_URLS:
        raise EnvironmentError(f"지원하지 않는 API 서비스입니다: {service}")

    env_name, default_url = _SERVICE_BASE_URLS[normalized]
    return validate_base_url(os.getenv(env_name, default_url))


def configured_api_base_urls() -> tuple[str, ...]:
    """인증정보 전송을 허용한 QA API 호스트 목록을 반환한다."""
    values = [require_service_base_url(name) for name in _SERVICE_BASE_URLS]
    # 게시판 레거시 API는 classroom API와 다른 QA 호스트를 사용할 수 있다.
    # 값이 명시된 경우에만 기존과 같은 QA 도메인/HTTPS 검증을 거쳐 허용한다.
    for env_name in ("LXP_API_BASE_URL", "LXP_LEGACY_API_BASE_URL"):
        legacy_url = os.getenv(env_name, "").strip()
        if legacy_url:
            values.append(validate_base_url(legacy_url))
    return tuple(values)


def require_org() -> str:
    """ORG_NAME_SHORT가 설정되어 있는지 확인 후 반환한다."""
    return _require("LXP_ORG_NAME_SHORT")


def require_classroom_id() -> str:
    """QA 전용 클래스 식별값이 설정됐는지 확인 후 반환한다."""
    return _require("LXP_CLASSROOM_ID")


def is_mutating_test_allowed() -> bool:
    """승인된 상태 변경 테스트만 명시적으로 허용한다."""
    return (
        os.getenv("LXP_ALLOW_MUTATING_REQUESTS", "").strip().lower() == "true"
        or os.getenv("LXP_ALLOW_MUTATING_TESTS", "").strip().lower() == "true"
    )
