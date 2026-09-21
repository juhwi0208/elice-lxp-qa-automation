"""TC80·TC81 기존 통합 API 수업 자료 조회 테스트."""

import pytest

from part1_api_automation.utils.legacy_course_api import LegacyCourseApi
from part1_api_automation.utils.response import assert_api_success


@pytest.mark.read_only
@pytest.mark.learner
def test_tc080_learner_lists_lecture_pages(
    lecture_id: int,
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
    lecture_locator_type: int,
) -> None:
    """TC80: 대상 수업에 속한 자료 목록과 전체 개수를 반환한다."""
    response = legacy_course_api.list_lecture_pages(
        lecture_id,
        lecture_locator_type,
        learner_headers,
        offset=0,
        count=20,
    )
    body = assert_api_success(response, expected_api_status_code=200)

    page_count = body.get("lecture_page_count")
    pages = body.get("lecture_pages")
    assert isinstance(page_count, int) and page_count >= 0
    assert isinstance(pages, list)
    assert len(pages) <= 20
    assert all(page.get("lecture_id") == lecture_id for page in pages)


@pytest.mark.read_only
@pytest.mark.learner
def test_tc081_learner_reads_lecture_page_detail(
    lecture_page_id: int,
    legacy_course_api: LegacyCourseApi,
    learner_headers: dict,
) -> None:
    """TC81: 요청한 수업 자료의 ID·제목·공개 상태를 반환한다."""
    response = legacy_course_api.get_lecture_page(
        lecture_page_id,
        learner_headers,
    )
    if response.ok:
        try:
            response_body = response.json()
        except ValueError:
            response_body = {}
        fail_code = response_body.get("fail_code")
        if fail_code == "ready_test_admission_status":
            pytest.skip(
                "학습자 TEST 시작 전 상태(Ready): 시험 시작 후 실행해야 합니다."
            )
        if fail_code == "not_accessible_test":
            pytest.skip(
                "학습자 TEST 완료 상태(Completed): 재응시 가능 상태로 전환한 뒤 "
                "실행해야 합니다."
            )
    body = assert_api_success(response, expected_api_status_code=200)

    page = body.get("lecture_page")
    assert isinstance(page, dict)
    assert page.get("id") == lecture_page_id
    assert isinstance(page.get("title"), str) and page["title"].strip()
    assert isinstance(page.get("is_opened"), bool)
