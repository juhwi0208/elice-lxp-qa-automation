"""브라우저 E2E 테스트 설정과 역할별 계정정보 로더."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID


class E2EConfigurationError(EnvironmentError):
    """E2E 필수 설정이 없거나 안전 규칙을 위반했을 때 발생한다."""


@dataclass(frozen=True)
class E2ESettings:
    accounts_base_url: str
    web_base_url: str
    org_name_short: str


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str

    def __repr__(self) -> str:
        return f"Credentials(email={self.email!r}, password=<redacted>)"


@dataclass(frozen=True)
class ClassroomContext:
    """여러 E2E 기능이 공통으로 사용하는 테스트 대상 강의실."""

    classroom_id: str


@dataclass(frozen=True)
class CourseTestData:
    """학습과목 E2E에서 사용하는 QA 전용 Dummy 데이터."""

    course_name: str
    test_lecture_name: str
    test_answer: str


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise E2EConfigurationError(
            f"필수 E2E 환경변수 {name}이 비어 있습니다. .env.example을 확인하세요."
        )
    return value


def _validate_e2e_base_url(value: str) -> str:
    """E2E 계정정보를 전송해도 되는 HTTPS QA 호스트만 반환한다."""
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    allowed_suffix = "dev.elicer.io"

    if parsed.scheme != "https":
        raise E2EConfigurationError("E2E 기본 URL은 HTTPS 주소여야 합니다.")
    if not host or not (
        host == allowed_suffix or host.endswith(f".{allowed_suffix}")
    ):
        raise E2EConfigurationError(
            f"E2E 기본 URL은 승인된 QA 도메인(*.{allowed_suffix})이어야 합니다."
        )
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise E2EConfigurationError(
            "E2E 기본 URL에는 사용자 정보나 별도 포트를 포함할 수 없습니다."
        )
    if parsed.params or parsed.query or parsed.fragment:
        raise E2EConfigurationError(
            "E2E 기본 URL에는 파라미터, 쿼리 또는 프래그먼트를 포함할 수 없습니다."
        )
    return normalized


def load_e2e_settings() -> E2ESettings:
    """승인된 QA 호스트와 기관 설정을 로드한다."""
    accounts_url = os.getenv(
        "LXP_ACCOUNTS_BASE_URL",
        "https://dev-qatrack-accounts.dev.elicer.io",
    )
    web_url = os.getenv(
        "LXP_WEB_BASE_URL",
        "https://dev-qatrack-web.dev.elicer.io",
    )
    org_name = _required("LXP_ORG_NAME_SHORT")

    return E2ESettings(
        accounts_base_url=_validate_e2e_base_url(accounts_url),
        web_base_url=_validate_e2e_base_url(web_url),
        org_name_short=org_name,
    )


def load_credentials(role: str) -> Credentials:
    """학습자 또는 교육자 QA 계정정보를 환경변수에서 로드한다."""
    normalized_role = role.strip().upper()
    if normalized_role not in {"LEARNER", "EDUCATOR"}:
        raise E2EConfigurationError(f"지원하지 않는 E2E 역할입니다: {role}")

    return Credentials(
        email=_required(f"LXP_{normalized_role}_EMAIL"),
        password=_required(f"LXP_{normalized_role}_PASSWORD"),
    )


def load_classroom_context() -> ClassroomContext:
    """강의실 기능 테스트에 사용할 UUID를 검증해서 로드한다."""
    classroom_id = _required("LXP_CLASSROOM_ID")
    try:
        UUID(classroom_id)
    except ValueError as exc:
        raise E2EConfigurationError(
            "LXP_CLASSROOM_ID는 유효한 강의실 UUID여야 합니다."
        ) from exc

    return ClassroomContext(classroom_id=classroom_id)


def load_course_test_data() -> CourseTestData:
    """TC에 지정된 학습과목 Dummy 데이터 이름을 로드한다."""
    return CourseTestData(
        course_name=os.getenv("LXP_COURSE_NAME", "SANDBOX").strip() or "SANDBOX",
        test_lecture_name=(
            os.getenv("LXP_TEST_LECTURE_NAME", "TEST").strip() or "TEST"
        ),
        test_answer=os.getenv("LXP_TEST_ANSWER", "").strip(),
    )
