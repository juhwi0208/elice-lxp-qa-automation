"""학습자·교육자 QA 계정의 로그인 화면 E2E 테스트."""

import pytest

from part3_e2e.config import Credentials
from part3_e2e.pages.login_page import LoginPage


@pytest.mark.e2e
@pytest.mark.login
@pytest.mark.learner
def test_learner_can_login(
    login_page: LoginPage,
    learner_credentials: Credentials,
) -> None:
    """학습자 QA 계정이 로그인 화면을 거쳐 LXP로 이동하는지 검증한다."""
    login_page.login_and_wait(learner_credentials)


@pytest.mark.e2e
@pytest.mark.login
@pytest.mark.educator
def test_educator_can_login(
    login_page: LoginPage,
    educator_credentials: Credentials,
) -> None:
    """교육자 QA 계정이 로그인 화면을 거쳐 LXP로 이동하는지 검증한다."""
    login_page.login_and_wait(educator_credentials)
