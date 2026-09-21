"""
token_manager.py
학습자/교육자 인증 토큰을 관리한다.

토큰 획득 순서:
1. 환경변수의 로그인 계정(EMAIL/PASSWORD)으로 Account API 자동 로그인을 시도한다.
2. 로그인 성공 시 응답의 access_token을 사용한다.
3. 자동 로그인 실패 시 환경변수의 수동 토큰을 fallback으로 사용한다.
4. 자동 로그인과 fallback 토큰 사용이 모두 불가능하면
   TokenNotSetError를 발생시켜 테스트를 중단한다.

보안 원칙:
- 실제 이메일, 비밀번호, 토큰 값은 코드·로그·커밋에 포함하지 않는다.
- 자동 발급받은 토큰은 .env에 저장하지 않고 현재 프로세스 메모리에만 캐싱한다.
- 동일 프로세스에서는 학습자/교육자별로 최초 1회만 토큰을 획득한다.
"""

import os

from dotenv import load_dotenv

from part1_api_automation.utils import api_client


load_dotenv()


# 세션 내 토큰 캐시
_learner_token_cache: str | None = None
_educator_token_cache: str | None = None
_other_learner_token_cache: str | None = None


class TokenNotSetError(EnvironmentError):
    """자동 로그인과 fallback 토큰 사용이 모두 불가능할 때 발생하는 예외."""


class InvalidTokenError(ValueError):
    """토큰 형식이 안전하지 않을 때 발생하는 예외."""


class LoginError(RuntimeError):
    """자동 로그인 과정에서 발생하는 예외."""


class RedactedAuthHeaders(dict):
    """요청에는 실제 값을 쓰되 실패 리포트에서는 인증값을 숨기는 헤더."""

    def __repr__(self) -> str:
        safe = dict(self)
        for key in tuple(safe):
            if key.lower() in {"authorization", "x-api-key"}:
                safe[key] = "<redacted>"
        return repr(safe)


def _normalize_token(token: str) -> str:
    """
    Bearer 접두사를 제거하고 헤더에 사용할 토큰 원문만 반환한다.
    """
    normalized = token.strip()

    if normalized.lower().startswith("bearer "):
        normalized = normalized[7:].strip()

    if not normalized:
        raise InvalidTokenError("인증 토큰이 비어 있습니다.")

    if any(character.isspace() for character in normalized):
        raise InvalidTokenError("인증 토큰에는 공백이나 줄바꿈을 포함할 수 없습니다.")

    return normalized


def _require_account_api_base_url() -> str:
    """
    Account API Base URL을 환경변수에서 읽어 반환한다.

    환경변수:
        LXP_ACCOUNT_API_BASE_URL
    """
    base_url = os.getenv("LXP_ACCOUNT_API_BASE_URL", "").strip()

    if not base_url:
        raise LoginError(
            "Account API 주소(LXP_ACCOUNT_API_BASE_URL)가 설정되지 않았습니다."
        )

    return base_url.rstrip("/")


def _login(login_id: str, password: str) -> str:
    """
    Account API에 로그인하고 access_token을 반환한다.

    공용 api_client._request()를 통해 호출하므로
    타임아웃·호출 간격·5xx 중단 정책이 자동 적용된다.
    비밀번호·토큰 값은 이 함수 내에서만 처리하고 로그에 남기지 않는다.

    API:
        POST /login/pw
    """
    login_id = login_id.strip()
    password = password.strip()

    if not login_id or not password:
        raise LoginError(
            "자동 로그인에 필요한 이메일 또는 비밀번호가 설정되지 않았습니다."
        )

    url = f"{_require_account_api_base_url()}/login/pw"

    # 로그인 엔드포인트는 인증 헤더 없이 호출한다.
    # _request()는 타임아웃·간격·5xx 중단을 공통으로 적용한다.
    # mutating 안전 체크는 로그인 특성상 우회(confirmed=True)한다.
    try:
        response = api_client.post_password_login(
            url,
            login_id=login_id,
            password=password,
        )
    except Exception as exc:
        raise LoginError(
            f"자동 로그인 요청 중 오류가 발생했습니다. 오류 종류: {type(exc).__name__}"
        ) from exc

    if not response.ok:
        raise LoginError(f"자동 로그인에 실패했습니다. HTTP {response.status_code}")

    try:
        body = response.json()
    except ValueError as exc:
        raise LoginError("로그인 API 응답이 올바른 JSON 형식이 아닙니다.") from exc

    access_token = body.get("access_token")

    if not isinstance(access_token, str) or not access_token.strip():
        raise LoginError("로그인 API 응답에 access_token이 없습니다.")

    return _normalize_token(access_token)


def _get_fallback_token(env_name: str) -> str:
    """
    자동 로그인 실패 시 환경변수의 fallback 토큰을 반환한다.
    """
    token = os.getenv(env_name, "").strip()

    if not token:
        raise TokenNotSetError(f"fallback 토큰({env_name})이 설정되지 않았습니다.")

    return _normalize_token(token)


def _get_token(
    *,
    login_id_env: str,
    password_env: str,
    fallback_token_env: str,
    role_name: str,
) -> str:
    """
    역할별 인증 토큰을 획득한다.

    1. 자동 로그인 시도
    2. 실패 시 fallback 토큰 사용
    3. 둘 다 실패하면 TokenNotSetError 발생
    """
    login_id = os.getenv(login_id_env, "")
    password = os.getenv(password_env, "")

    try:
        return _login(login_id, password)

    except LoginError as login_error:
        try:
            return _get_fallback_token(fallback_token_env)

        except (TokenNotSetError, InvalidTokenError) as fallback_error:
            raise TokenNotSetError(
                f"{role_name} 인증에 실패했습니다. "
                f"자동 로그인에 실패했고 "
                f"fallback 토큰({fallback_token_env})도 사용할 수 없습니다. "
                f"자동 로그인 오류: {login_error}"
            ) from fallback_error


def get_learner_token() -> str:
    """
    학습자 인증 토큰을 반환한다.

    우선순위:
    1. LXP_LEARNER_EMAIL / LXP_LEARNER_PASSWORD 자동 로그인
    2. LXP_LEARNER_TOKEN fallback

    동일 프로세스에서는 최초 1회만 토큰을 획득한다.
    """
    global _learner_token_cache

    if _learner_token_cache is None:
        _learner_token_cache = _get_token(
            login_id_env="LXP_LEARNER_EMAIL",
            password_env="LXP_LEARNER_PASSWORD",
            fallback_token_env="LXP_LEARNER_TOKEN",
            role_name="학습자",
        )

    return _learner_token_cache


def get_educator_token() -> str:
    """
    교육자 인증 토큰을 반환한다.

    우선순위:
    1. LXP_EDUCATOR_EMAIL / LXP_EDUCATOR_PASSWORD 자동 로그인
    2. LXP_EDUCATOR_TOKEN fallback

    동일 프로세스에서는 최초 1회만 토큰을 획득한다.
    """
    global _educator_token_cache

    if _educator_token_cache is None:
        _educator_token_cache = _get_token(
            login_id_env="LXP_EDUCATOR_EMAIL",
            password_env="LXP_EDUCATOR_PASSWORD",
            fallback_token_env="LXP_EDUCATOR_TOKEN",
            role_name="교육자",
        )

    return _educator_token_cache


def get_other_learner_token() -> str:
    """
    두 번째 학습자 인증 토큰을 반환한다.

    우선순위:
    1. LXP_OTHER_LEARNER_EMAIL / LXP_OTHER_LEARNER_PASSWORD 자동 로그인
    2. LXP_OTHER_LEARNER_TOKEN fallback

    동일 프로세스에서는 최초 1회만 토큰을 획득한다.
    """
    global _other_learner_token_cache

    if _other_learner_token_cache is None:
        _other_learner_token_cache = _get_token(
            login_id_env="LXP_OTHER_LEARNER_EMAIL",
            password_env="LXP_OTHER_LEARNER_PASSWORD",
            fallback_token_env="LXP_OTHER_LEARNER_TOKEN",
            role_name="두 번째 학습자",
        )

    return _other_learner_token_cache


def learner_auth_header() -> dict:
    """학습자 Bearer 인증 헤더를 반환한다."""
    return RedactedAuthHeaders(
        {"Authorization": f"Bearer {get_learner_token()}"}
    )


def educator_auth_header() -> dict:
    """교육자 Bearer 인증 헤더를 반환한다."""
    return RedactedAuthHeaders(
        {"Authorization": f"Bearer {get_educator_token()}"}
    )


def other_learner_auth_header() -> dict:
    """두 번째 학습자 Bearer 인증 헤더를 반환한다."""
    return RedactedAuthHeaders(
        {"Authorization": f"Bearer {get_other_learner_token()}"}
    )
