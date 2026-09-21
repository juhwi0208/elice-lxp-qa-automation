"""E2E 통합 테스트 - [일정] 도메인 (단계 24~44, 77~84)
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta
from uuid import uuid4

import allure
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait

from part1_api_automation.tests.board.helpers import article_get_url, multipart
from part1_api_automation.utils import api_client
from part3_e2e.config import ClassroomContext, CourseTestData, Credentials, E2ESettings
from part3_e2e.fixtures.tc_result_collector import TCResultCollector
from part3_e2e.pages.board_page import BoardPage
from part3_e2e.pages.class_schedule_page import ClassSchedulePage
from part3_e2e.pages.classroom_home_page import ClassroomHomePage, WidgetSnapshot
from part3_e2e.pages.common.app_shell import AppShell
from part3_e2e.pages.common.base_page import build_web_url
from part3_e2e.pages.common.selenium_support import (
    accessible_name,
    click_when_ready,
    role_elements,
    text_elements,
    wait_text,
)
from part3_e2e.pages.course_detail_page import CourseDetailPage
from part3_e2e.pages.course_list_page import CourseListPage
from part3_e2e.pages.course_management_page import CourseManagementPage
from part3_e2e.pages.login_page import LoginPage
from test_support.cleanup import CleanupRegistry

from part3_e2e.tests.e2e_integration.e2e_helpers import *

@pytest.mark.e2e
@pytest.mark.educator
@pytest.mark.learner
class TestScheduleSteps:
    def test_excel_schedule_steps_flow(
        self,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
        educator_app_shell: AppShell,
        admin_app_shell: AppShell,
        learner_credentials: Credentials,
        e2e_settings: E2ESettings,
        classroom_context: ClassroomContext,
        course_test_data: CourseTestData,
        integration_state: dict,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """Excel ``전체 기능(E2E 통합)`` [SCHEDULE] 도메인 연속 검증."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=24, end_step=84)
        data = integration_data
        learner = learner_app_shell
        educator = educator_app_shell
        admin = admin_app_shell
        classroom_id = classroom_context.classroom_id
        course = course_test_data.course_name
        lesson = course_test_data.test_lecture_name
        normal_title = f"{_QA_PREFIX} 일반-{uuid4().hex[:8]}"
        normal_body = f"{_QA_PREFIX} 본문-{uuid4().hex}"
        secret_title = f"{_QA_PREFIX} 비밀-{uuid4().hex[:8]}"
        secret_body = f"{_QA_PREFIX} 교육자 전용-{uuid4().hex}"
        schedule_title = f"{_QA_PREFIX} 일정-{uuid4().hex[:8]}"
        recurring_title = f"{_QA_PREFIX} 반복-{uuid4().hex[:8]}"
        all_day_title = f"{_QA_PREFIX} 종일-{uuid4().hex[:8]}"
        temporary_course_name = data.temporary_course_name
        try:
            for stale in _schedule_list(data, classroom_id, educator=True):
                stale_title = str(stale.get("summary", ""))
                if (
                    (stale_title.startswith(_QA_PREFIX) and stale_title not in data.multi_schedule_titles)
                    or stale_title == "Untitled"
                ):
                    _delete_schedule(data, classroom_id, stale["id"])

            with c.step(24, "교육자 일정 폼 입력 후 취소 시 UI·API 미생성"):
                educator_schedule = ClassSchedulePage(educator)
                schedule_before = _schedule_list(data, classroom_id, educator=True)
                cancel_title = f"{_QA_PREFIX} 취소-{uuid4().hex[:8]}"
                educator_schedule.open(); educator_schedule.click_create_schedule_button()
                educator_schedule.fill_schedule_form(title=cancel_title, description="취소 검증")
                _schedule_times(educator.driver, data.schedule_start, data.schedule_end)
                assert any(
                    element.get_attribute("value") == cancel_title
                    for element in _visible(educator.driver, By.CSS_SELECTOR, "input[name='summary'],input[placeholder*='제목']")
                )
                educator_schedule.cancel_schedule_form()
                assert not _schedule_matches(data, classroom_id, cancel_title, educator=True)
                assert {item.get("id") for item in _schedule_list(data, classroom_id, educator=True)} == {item.get("id") for item in schedule_before}

            with c.step(25, "일정 제목 필수와 종료≤시작 유효성·미생성"):
                educator_schedule.click_create_schedule_button()
                educator_schedule.fill_schedule_form(title="", description="필수값 검증")
                _schedule_times(educator.driver, data.schedule_start, data.schedule_end)
                educator_schedule.submit_schedule_form()
                time.sleep(1)
                assert educator_schedule.has_validation_error() or bool(_errors(educator.driver)) or educator_schedule.is_form_open()
                educator_schedule.cancel_schedule_form()
                invalid_title = f"{_QA_PREFIX} 역전-{uuid4().hex[:8]}"
                educator_schedule.click_create_schedule_button()
                educator_schedule.fill_schedule_form(title=invalid_title, description="종료시각 검증")
                _schedule_times(educator.driver, data.schedule_end, data.schedule_start)
                educator_schedule.submit_schedule_form()
                time.sleep(1)
                assert bool(_errors(educator.driver)) or educator_schedule.is_form_open()
                assert not _schedule_matches(data, classroom_id, invalid_title, educator=True)
                educator_schedule.cancel_schedule_form()

            with c.step(26, "빈 10분 구간에 임시 일정 정확히 하나 생성·UI/API 일치"):
                integration_cleanup.add(
                    key="temporary-schedule",
                    description="QA 임시 일정 삭제",
                    callback=lambda: _delete_schedules_by_title(data, classroom_id, schedule_title),
                )
                created = _create_schedule(
                    educator_schedule,
                    data,
                    classroom_id,
                    title=schedule_title,
                    start=data.schedule_start,
                    end=data.schedule_end,
                    description="QA 일정 원본 설명",
                )
                schedule_id = created["id"]
                integration_state["schedule_id"] = schedule_id
                integration_cleanup.add(
                    key="temporary-schedule-id",
                    description="QA 임시 일정 ID 삭제",
                    callback=lambda: _delete_schedule(data, classroom_id, schedule_id),
                )
                educator_schedule.open()
                assert educator_schedule.is_title_present_in_calendar(schedule_title)
                educator_schedule.click_schedule_card_by_title(schedule_title)
                _expect_schedule_detail_title(educator.driver, schedule_title)
                assert data.schedule_start.strftime("%H:%M") in educator_schedule.get_detail_time()

            with c.step(27, "임시 일정의 월/주/목록 보기 제목·날짜·시간 일치"):
                expected_text = (schedule_title, data.schedule_start.strftime("%m"), data.schedule_start.strftime("%d"), data.schedule_start.strftime("%H:%M"))
                view_texts = []
                _close_schedule_detail(educator.driver, schedule_title)
                for pattern in (r"^월$|월간", r"^주$|주간", r"^목록$"):
                    _click_named(educator.driver, educator.driver, pattern)
                    WebDriverWait(educator.driver, _SHORT_WAIT).until(lambda d: schedule_title in _body(d))
                    current = _body(educator.driver)
                    assert schedule_title in current
                    view_texts.append(current)
                assert all(any(piece in view for piece in expected_text[1:]) for view in view_texts)
                assert len(_schedule_matches(data, classroom_id, schedule_title, educator=True)) == 1

            with c.step(28, "임시 일정 제목 하나만 수정하고 UI/API에서 다른 필드 불변"):
                edited_title = schedule_title + "-수정"
                before_item = _schedule_matches(data, classroom_id, schedule_title, educator=True)[0]
                educator_schedule.open(); educator_schedule.click_schedule_card_by_title(schedule_title)
                educator_schedule.click_edit_schedule()
                educator_schedule.fill_schedule_form(title=edited_title)
                educator_schedule.submit_schedule_form()
                matches = _schedule_matches(data, classroom_id, edited_title, educator=True)
                assert len(matches) == 1 and not _schedule_matches(data, classroom_id, schedule_title, educator=True)
                after_item = matches[0]
                for field in ("id", "dt_start", "dt_end", "description"):
                    assert after_item.get(field) == before_item.get(field), f"제목 외 {field}가 변경됐습니다."
                assert educator_schedule.is_title_present_in_calendar(edited_title)
                integration_state["edited_schedule_title"] = edited_title

            with c.step(29, "일정 수정값 새로고침 영속성과 기존 일정 비변경"):
                current_schedule_ids = {item.get("id") for item in _schedule_list(data, classroom_id, educator=True)}
                educator.driver.refresh(); educator_schedule.wait_until_loaded()
                assert educator_schedule.is_title_present_in_calendar(edited_title)
                assert len(_schedule_matches(data, classroom_id, edited_title, educator=True)) == 1
                assert {item.get("id") for item in _schedule_list(data, classroom_id, educator=True)} == current_schedule_ids

            with c.step(30, "일정 수정 후 취소 시 제목·시간 원본 유지"):
                exact_before_cancel = _schedule_matches(data, classroom_id, edited_title, educator=True)[0]
                educator_schedule.click_schedule_card_by_title(edited_title)
                educator_schedule.click_edit_schedule()
                educator_schedule.fill_schedule_form(title=edited_title + "-취소")
                _schedule_times(educator.driver, data.schedule_start + timedelta(hours=1), data.schedule_end + timedelta(hours=1))
                educator_schedule.cancel_schedule_form()
                assert _schedule_matches(data, classroom_id, edited_title, educator=True) == [exact_before_cancel]
                assert not _schedule_matches(data, classroom_id, edited_title + "-취소", educator=True)

            with c.step(31, "일정 설명만 수정하고 제목·시각·ID 유지"):
                description = f"{_QA_PREFIX} 설명-{uuid4().hex[:8]}"
                educator_schedule.open(); educator_schedule.click_schedule_card_by_title(edited_title)
                educator_schedule.click_edit_schedule()
                old_description = _schedule_description(educator.driver, description)
                educator_schedule.submit_schedule_form()
                described = _schedule_matches(data, classroom_id, edited_title, educator=True)[0]
                assert described.get("description") == description
                for field in ("id", "summary", "dt_start", "dt_end"):
                    assert described.get(field) == exact_before_cancel.get(field)
                integration_state["schedule_original_description"] = old_description

            with c.step(32, "일정 삭제 확인창 취소 후 유지, 재삭제 확인 후 완전 제거"):
                educator_schedule.open(); educator_schedule.click_schedule_card_by_title(edited_title)
                educator_schedule.click_delete_schedule()
                assert _visible(educator.driver, By.CSS_SELECTOR, "[role='dialog'],.MuiDialog-paper")
                educator_schedule.cancel_delete()
                assert len(_schedule_matches(data, classroom_id, edited_title, educator=True)) == 1
                educator_schedule.click_schedule_card_by_title(edited_title)
                educator_schedule.click_delete_schedule(); educator_schedule.confirm_delete()
                assert not _schedule_matches(data, classroom_id, edited_title, educator=True)
                assert educator_schedule.wait_title_disappears(edited_title)

            with c.step(33, "제한된 반복 일정 저장 또는 명확한 정책 차단"):
                integration_cleanup.add(
                    key="recurring-schedule",
                    description="QA 반복 일정 삭제",
                    callback=lambda: _delete_schedules_by_title(data, classroom_id, recurring_title),
                )
                educator_schedule.open(); educator_schedule.click_create_schedule_button()
                educator_schedule.fill_schedule_form(title=recurring_title, description="제한 반복 검증")
                _schedule_times(educator.driver, data.schedule_start, data.schedule_end)
                _schedule_option(educator.driver, r"반복|repeat", True)
                date_inputs = _visible(educator.driver, By.CSS_SELECTOR, "[role='dialog'] input[type='date'],.MuiPopover-paper input[type='date']")
                if len(date_inputs) >= 3:
                    _native(educator.driver, date_inputs[-1], data.recurring_until.strftime("%Y-%m-%d"))
                dialogs = _visible(educator.driver, By.CSS_SELECTOR, "[role='dialog'],.MuiDialog-paper,.MuiPopover-paper")
                _click_named(dialogs[-1] if dialogs else educator.driver, educator.driver, r"^(저장|확인|완료)$")
                time.sleep(2)
                recurrence_items = _schedule_matches(data, classroom_id, recurring_title, educator=True)
                if recurrence_items:
                    integration_state["recurrence_policy"] = "created"
                    assert all(item.get("id") for item in recurrence_items)
                else:
                    integration_state["recurrence_policy"] = "blocked"
                    integration_state["recurrence_error"] = _errors(educator.driver)
                    assert re.search(r"반복|지원|저장|기간|종료|사용할 수 없", integration_state["recurrence_error"])
                    if educator_schedule.is_form_open():
                        educator_schedule.cancel_schedule_form()

            with c.step(34, "반복 규칙·인스턴스 또는 차단 결과의 캘린더/목록/상세/API 일치"):
                recurrence_items = _schedule_matches(data, classroom_id, recurring_title, educator=True)
                if integration_state["recurrence_policy"] == "created":
                    assert recurrence_items
                    for item in recurrence_items:
                        assert item.get("summary") == recurring_title
                        assert datetime.fromisoformat(str(item["dt_start"]).replace("Z", "+00:00")).date() <= data.recurring_until.date()
                    educator_schedule.open()
                    assert educator_schedule.is_title_present_in_calendar(recurring_title)
                    educator_schedule.switch_to_list_view()
                    assert recurring_title in _body(educator.driver)
                else:
                    assert not recurrence_items
                    assert integration_state["recurrence_error"]

            with c.step(35, "종일 일정 생성과 날짜 경계·종일 표시 정확성"):
                all_day_start = data.all_day_date.replace(hour=0, minute=0, second=0, microsecond=0)
                all_day_end = all_day_start + timedelta(days=1)
                integration_cleanup.add(
                    key="all-day-schedule",
                    description="QA 종일 일정 삭제",
                    callback=lambda: _delete_schedules_by_title(data, classroom_id, all_day_title),
                )
                all_day_item = _create_schedule(
                    educator_schedule,
                    data,
                    classroom_id,
                    title=all_day_title,
                    start=all_day_start,
                    end=all_day_end,
                    description="종일 검증",
                    all_day=True,
                )
                assert all_day_item.get("is_all_day") is True or all_day_item.get("all_day") is True
                educator_schedule.open(); educator_schedule.click_schedule_card_by_title(all_day_title)
                assert re.search(r"종일|하루", _body(educator.driver))

            with c.step(36, "교육자 일정 생성·수정·삭제·보기 관리 UI 노출"):
                _close_schedule_detail(educator.driver, all_day_title)
                assert educator_schedule.is_create_button_visible()
                educator_schedule.click_schedule_card_by_title(all_day_title)
                controls = " ".join(accessible_name(e) for e in _visible(educator.driver, By.CSS_SELECTOR, "button,[role='button']"))
                assert re.search(r"수정|편집|edit", controls, re.I)
                assert re.search(r"삭제|delete", controls, re.I)
                _close_schedule_detail(educator.driver, all_day_title)
                assert any(re.search(r"월|주|목록", accessible_name(e)) for e in _visible(educator.driver, By.CSS_SELECTOR, "button,[role='button']"))

            with c.step(37, "학습자 일정에서 교육자 생성 종일 일정 단일 표시·상세·목록 일치"):
                learner_schedule = ClassSchedulePage(learner)
                learner_schedule.open()
                assert learner_schedule.is_title_present_in_calendar(all_day_title)
                learner_schedule.click_schedule_card_by_title(all_day_title)
                _expect_schedule_detail_title(learner.driver, all_day_title)
                assert re.search(r"종일|하루", _body(learner.driver))
                _close_schedule_detail(learner.driver, all_day_title); learner_schedule.switch_to_list_view()
                assert _body(learner.driver).count(all_day_title) == 1
                assert len(_schedule_matches(data, classroom_id, all_day_title, educator=False)) == 1

            with c.step(38, "데이터 없는 기간 이동·빈 상태·오늘 복귀"):
                learner_schedule.switch_to_calendar_view()
                for _ in range(data.empty_period_moves):
                    learner_schedule.go_to_next_period()
                assert learner_schedule.is_empty_state_visible() or not _cards(learner_schedule)
                assert not re.search(r"오류|에러|exception|500", _body(learner.driver), re.I)
                learner_schedule.go_to_today()
                assert _today(learner.driver)
                assert learner_schedule.is_title_present_in_calendar(all_day_title)

            with c.step(39, "보기 단위 또는 주말 토글·이동·오늘 복귀 정확성"):
                initial_period = _period(learner.driver)
                initial_cards = _cards(learner_schedule)
                view_buttons = [e for e in role_elements(learner.driver, "button", re.compile(r"월|주|목록|주말")) if e.is_displayed()]
                assert view_buttons
                if any("주말" in accessible_name(e) for e in view_buttons):
                    learner_schedule.toggle_weekend(); toggled_period = _period(learner.driver)
                    learner_schedule.toggle_weekend()
                else:
                    _click_named(learner.driver, learner.driver, r"주")
                    toggled_period = _period(learner.driver)
                assert toggled_period
                learner_schedule.go_to_next_period(); learner_schedule.go_to_today()
                assert _period(learner.driver) == initial_period
                assert _cards(learner_schedule) == initial_cards
                assert _today(learner.driver)

            with c.step(40, "동일 날짜 복수 일정의 상세·목록 정렬·시간 일치"):
                api_items = _schedule_list(data, classroom_id, educator=False)
                multi = [item for item in api_items if item.get("summary") in data.multi_schedule_titles]
                assert {item.get("summary") for item in multi} == set(data.multi_schedule_titles)
                dates = {datetime.fromisoformat(str(item["dt_start"]).replace("Z", "+00:00")).date() for item in multi}
                assert len(dates) == 1
                expected_order = tuple(item["summary"] for item in sorted(multi, key=lambda item: item["dt_start"]))
                learner_schedule.open(); learner_schedule.go_to_today(); learner_schedule.switch_to_list_view()
                body = _body(learner.driver)
                positions = [body.index(title) for title in expected_order]
                assert positions == sorted(positions)
                for item in multi:
                    learner_schedule.click_schedule_card_by_title(item["summary"])
                    _expect_schedule_detail_title(learner.driver, item["summary"])
                    assert datetime.fromisoformat(str(item["dt_start"]).replace("Z", "+00:00")).strftime("%H:%M") in learner_schedule.get_detail_time()
                    _close_schedule_detail(learner.driver, item["summary"])

            with c.step(41, "일정 새로고침·메뉴 왕복 후 로그인/기간/데이터 유지·중복 없음"):
                learner_schedule.open(); period_before = _period(learner.driver); cards_before = _cards(learner_schedule)
                learner.driver.refresh(); learner_schedule.wait_until_loaded()
                assert _period(learner.driver) == period_before and _cards(learner_schedule) == cards_before
                BoardPage(learner).open(); learner_schedule.open()
                assert _period(learner.driver) == period_before and _cards(learner_schedule) == cards_before
                assert len(cards_before) == len(set(cards_before))
                assert not re.search(r"로그인", learner.driver.current_url, re.I)

            with c.step(42, "일정 카드 키보드 Enter/Space 열기·닫기와 초점 복귀"):
                learner_schedule.open()
                matches = [e for e in text_elements(learner.driver, data.baseline_schedule_title, exact=False) if e.is_displayed()]
                assert matches
                card = _ancestor(learner.driver, matches[-1])
                card = _focus_activate(learner.driver, card)
                _expect_schedule_detail_title(learner.driver, data.baseline_schedule_title)
                close_buttons = [e for e in role_elements(learner.driver, "button", re.compile(r"닫기|close", re.I)) if e.is_displayed()]
                assert close_buttons
                _focus_activate(learner.driver, close_buttons[-1])
                _focus_returned(learner.driver, card)

            with c.step(43, "교육자 생성 종일·반복 일정의 학습자 공개 정책 일치"):
                learner_schedule.open()
                assert learner_schedule.is_title_present_in_calendar(all_day_title)
                assert len(_schedule_matches(data, classroom_id, all_day_title, educator=False)) == 1
                learner_recurrence = _schedule_matches(data, classroom_id, recurring_title, educator=False)
                if integration_state["recurrence_policy"] == "created":
                    assert learner_recurrence
                    assert learner_schedule.is_title_present_in_calendar(recurring_title)
                else:
                    assert not learner_recurrence

            with c.step(44, "학습자 일정 생성·수정·삭제 UI/관리 URL 차단 및 목록 불변"):
                learner_schedule.open()
                before_learner_schedules = _schedule_list(data, classroom_id, educator=False)
                assert not learner_schedule.is_create_button_visible(timeout=3)
                management_labels = " ".join(accessible_name(e) for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='button']"))
                assert not re.search(r"일정\s*(만들기|추가|수정|삭제)", management_labels)
                schedule_admin_url = build_web_url(e2e_settings, f"/classrooms/{classroom_id}/schedules/manage")
                learner.driver.get(schedule_admin_url)
                time.sleep(1)
                blocked = _body(learner.driver)
                assert (
                    re.search(r"권한|접근.*불가|403|찾을 수 없|로그인", blocked)
                    or learner.driver.current_url != schedule_admin_url
                    or not learner_schedule.is_create_button_visible(timeout=1)
                )
                assert _schedule_list(data, classroom_id, educator=False) == before_learner_schedules

            with c.step(77, "일정 이전/다음 이동 후 오늘 복귀·현재 주/오늘 강조"):
                learner_schedule = ClassSchedulePage(learner); learner_schedule.open(); learner_schedule.go_to_today()
                current_period = _period(learner.driver)
                learner_schedule.go_to_prev_period(); assert _period(learner.driver) != current_period
                learner_schedule.go_to_next_period(); assert _period(learner.driver) == current_period
                learner_schedule.go_to_today()
                assert _period(learner.driver) == current_period and _today(learner.driver)

            with c.step(78, "일정 이전→다음 왕복 후 기간·카드·오늘 강조와 중복 없음"):
                learner_schedule.go_to_today(); before_period = _period(learner.driver); before_cards = _cards(learner_schedule)
                learner_schedule.go_to_prev_period(); learner_schedule.go_to_next_period()
                assert _period(learner.driver) == before_period
                assert _cards(learner_schedule) == before_cards
                assert len(before_cards) == len(set(before_cards)) and _today(learner.driver)

            with c.step(79, "주말 끄기/켜기 전후 같은 기간·평일 일정 보존"):
                learner_schedule.go_to_today()
                period = _period(learner.driver)
                weekday_cells = tuple(e.get_attribute("data-date") for e in _visible(learner.driver, By.CSS_SELECTOR, "[data-date]") if e.get_attribute("data-date"))
                assert weekday_cells
                learner_schedule.toggle_weekend()
                assert _period(learner.driver) == period
                hidden_cells = tuple(e.get_attribute("data-date") for e in _visible(learner.driver, By.CSS_SELECTOR, "[data-date]") if e.get_attribute("data-date"))
                assert set(hidden_cells).issubset(set(weekday_cells))
                learner_schedule.toggle_weekend()
                restored_cells = tuple(e.get_attribute("data-date") for e in _visible(learner.driver, By.CSS_SELECTOR, "[data-date]") if e.get_attribute("data-date"))
                assert restored_cells == weekday_cells and _period(learner.driver) == period

            with c.step(80, "월/주/목록 보기 선택에 따른 헤더·배치·정보 변화"):
                view_signatures = {}
                for label, action in (
                    ("월", lambda: _click_named(learner.driver, learner.driver, r"^월$|월간")),
                    ("주", lambda: _click_named(learner.driver, learner.driver, r"^주$|주간")),
                    ("목록", learner_schedule.switch_to_list_view),
                ):
                    action()
                    signature = (_period(learner.driver), _cards(learner_schedule), len(_visible(learner.driver, By.CSS_SELECTOR, "[data-date],th,tbody tr")))
                    assert signature[0] and signature[2] > 0
                    view_signatures[label] = signature
                assert len(set(view_signatures.values())) >= 2

            with c.step(81, "월 경계가 걸린 주의 날짜·월 라벨·일정 배치 정확성"):
                learner_schedule.switch_to_calendar_view(); learner_schedule.go_to_today()
                boundary_dates = []
                for _ in range(8):
                    values = [e.get_attribute("data-date") for e in _visible(learner.driver, By.CSS_SELECTOR, "[data-date]") if e.get_attribute("data-date")]
                    months = {value[:7] for value in values if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)}
                    if len(months) >= 2:
                        boundary_dates = values
                        break
                    learner_schedule.go_to_next_period()
                assert boundary_dates
                assert all(value in learner.driver.page_source for value in set(boundary_dates))
                assert not re.search(r"NaN|Invalid Date", learner.driver.page_source)

            with c.step(82, "빠른 이전/다음 연속 조작 후 최종 선택 기간만 표시"):
                learner_schedule.go_to_today(); base_period = _period(learner.driver)
                learner_schedule.go_to_next_period(); expected_final = _period(learner.driver)
                learner_schedule.go_to_today()
                previous = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='button']") if re.search(r"이전|prev", accessible_name(e), re.I)]
                following = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='button']") if re.search(r"다음|next", accessible_name(e), re.I)]
                assert previous and following
                for control in (following[0], previous[0], following[0]):
                    learner.driver.execute_script("arguments[0].click()", control)
                WebDriverWait(learner.driver, _WAIT).until(lambda _: _period(learner.driver) == expected_final)
                time.sleep(1)
                assert _period(learner.driver) == expected_final and expected_final != base_period

            with c.step(83, "일정 상세 열기/닫기 후 기간·보기·스크롤 위치 유지"):
                learner_schedule.go_to_today(); learner_schedule.switch_to_list_view()
                period_before_detail = _period(learner.driver)
                learner.driver.execute_script("window.scrollTo(0, 240)")
                scroll_before = learner.driver.execute_script("return window.scrollY")
                learner_schedule.click_schedule_card_by_title(data.baseline_schedule_title)
                _expect_schedule_detail_title(learner.driver, data.baseline_schedule_title)
                _close_schedule_detail(learner.driver, data.baseline_schedule_title)
                assert _period(learner.driver) == period_before_detail
                assert learner.driver.execute_script("return window.scrollY") == scroll_before
                assert data.baseline_schedule_title in _body(learner.driver)

            with c.step(84, "일정 카드 Tab 포커스·Enter/Space 실제 열기/닫기"):
                matches = [e for e in text_elements(learner.driver, data.baseline_schedule_title, exact=False) if e.is_displayed()]
                assert matches
                card = _ancestor(learner.driver, matches[-1])
                card = _focus_activate(learner.driver, card)
                assert learner_schedule.get_detail_title() == data.baseline_schedule_title
                close = [e for e in role_elements(learner.driver, "button", re.compile(r"닫기|close", re.I)) if e.is_displayed()]
                assert close
                close[0].send_keys(Keys.SPACE)
                _focus_returned(learner.driver, card)

        finally:
            c.write()

    @pytest.mark.parametrize("step", (24, 25))
    def test_excel_schedule_validation_steps_independent(
        self,
        step: int,
        request,
        integration_data: IntegrationData,
        educator_app_shell: AppShell,
        classroom_context: ClassroomContext,
    ) -> None:
        """일정 미생성 검증은 각 케이스가 자체 폼만 열고 취소한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        data, educator = integration_data, educator_app_shell
        classroom_id = classroom_context.classroom_id
        schedule = ClassSchedulePage(educator)
        try:
            if step == 24:
                with c.step(24, "교육자 일정 폼 입력 후 취소 시 UI·API 미생성"):
                    before = _schedule_list(data, classroom_id, educator=True)
                    title = f"{_QA_PREFIX} 취소-{uuid4().hex[:8]}"
                    schedule.open(); schedule.click_create_schedule_button(); schedule.fill_schedule_form(title=title, description="취소 검증")
                    _schedule_times(educator.driver, data.schedule_start, data.schedule_end)
                    schedule.cancel_schedule_form()
                    assert not _schedule_matches(data, classroom_id, title, educator=True)
                    assert {item.get("id") for item in _schedule_list(data, classroom_id, educator=True)} == {item.get("id") for item in before}
            else:
                with c.step(25, "일정 제목 필수와 종료≤시작 유효성·미생성"):
                    schedule.open(); schedule.click_create_schedule_button(); schedule.fill_schedule_form(title="", description="필수값 검증")
                    _schedule_times(educator.driver, data.schedule_start, data.schedule_end)
                    schedule.submit_schedule_form(allow_disabled=True)
                    time.sleep(1)
                    assert schedule.has_validation_error() or bool(_errors(educator.driver)) or schedule.is_form_open()
                    schedule.cancel_schedule_form()
                    title = f"{_QA_PREFIX} 역전-{uuid4().hex[:8]}"; schedule.click_create_schedule_button()
                    schedule.fill_schedule_form(title=title, description="종료시각 검증")
                    _schedule_times(educator.driver, data.schedule_end, data.schedule_start)
                    schedule.submit_schedule_form(allow_disabled=True)
                    time.sleep(1)
                    assert bool(_errors(educator.driver)) or schedule.is_form_open()
                    assert not _schedule_matches(data, classroom_id, title, educator=True)
                    schedule.cancel_schedule_form()
        finally:
            try:
                if schedule.is_form_open():
                    schedule.cancel_schedule_form()
            except Exception:
                # Cleanup must not hide the original validation outcome.
                pass
            c.write()


    def test_excel_step_26_independent(
        self, request, integration_data: IntegrationData, educator_app_shell: AppShell,
        classroom_context: ClassroomContext, integration_cleanup: CleanupRegistry,
    ) -> None:
        """26번은 빈 QA 구간에 일정 하나를 만들고 ID로 삭제한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=26, end_step=26)
        data, educator = integration_data, educator_app_shell; schedule = ClassSchedulePage(educator); title = f"{_QA_PREFIX} 일정-{uuid4().hex[:8]}"
        try:
            with c.step(26, "빈 10분 구간에 임시 일정 정확히 하나 생성·UI/API 일치"):
                created = _create_schedule(schedule, data, classroom_context.classroom_id, title=title, start=data.schedule_start, end=data.schedule_end, description="QA 일정 원본 설명")
                schedule_id = created["id"]
                integration_cleanup.add(key="step26-schedule", description="26단계 임시 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, schedule_id))
                assert len(_schedule_matches(data, classroom_context.classroom_id, title, educator=True)) == 1
                schedule.open(); assert schedule.is_title_present_in_calendar(title); schedule.click_schedule_card_by_title(title)
                _expect_schedule_detail_title(educator.driver, title); assert data.schedule_start.strftime("%H:%M") in schedule.get_detail_time()
        finally:
            integration_cleanup.run()
            c.write()


    @pytest.mark.parametrize("step", (27, 28, 29, 30, 31, 32))
    def test_excel_schedule_mutation_steps_independent(
        self, step: int, request, integration_data: IntegrationData, educator_app_shell: AppShell,
        classroom_context: ClassroomContext, integration_cleanup: CleanupRegistry,
    ) -> None:
        """27~32번은 각 케이스가 임시 일정 하나를 생성하고 삭제한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        data, educator = integration_data, educator_app_shell; schedule = ClassSchedulePage(educator); title = f"{_QA_PREFIX} 일정-{uuid4().hex[:8]}"
        try:
            created = _create_schedule(schedule, data, classroom_context.classroom_id, title=title, start=data.schedule_start, end=data.schedule_end, description="QA 일정 원본 설명")
            schedule_id = created["id"]
            integration_cleanup.add(key=f"step{step}-schedule", description=f"{step}단계 임시 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, schedule_id))
            if step == 27:
                with c.step(27, "임시 일정의 캘린더/상세/목록 제목·날짜·시간 일치"):
                    schedule.open(); WebDriverWait(educator.driver, _SHORT_WAIT).until(lambda d: title in _body(d))
                    calendar_text = _body(educator.driver); assert title in calendar_text
                    schedule.click_schedule_card_by_title(title); _expect_schedule_detail_title(educator.driver, title)
                    detail_time = schedule.get_detail_time()
                    assert data.schedule_start.strftime("%H:%M") in detail_time or re.search(r"(?:오전|오후)\s*\d{1,2}:\d{2}", detail_time)
                    _close_schedule_detail(educator.driver, title)
                    schedule.switch_to_list_view()
                    list_text = WebDriverWait(educator.driver, _SHORT_WAIT).until(lambda d: title in _body(d) and _body(d))
                    assert title in list_text and str(data.schedule_start.day) in list_text
            elif step in (28, 29, 30, 31):
                edited = title + "-수정"; schedule.open(); schedule.click_schedule_card_by_title(title); schedule.click_edit_schedule(); schedule.fill_schedule_form(title=edited); schedule.submit_schedule_form()
                item = WebDriverWait(educator.driver, _WAIT).until(
                    lambda _: (_schedule_matches(data, classroom_context.classroom_id, edited, educator=True) or False)
                )[0]
                if step == 28:
                    with c.step(28, "임시 일정 제목 하나만 수정하고 UI/API에서 다른 필드 불변"):
                        for field in ("id", "dt_start", "dt_end", "description"): assert item.get(field) == created.get(field)
                        assert schedule.is_title_present_in_calendar(edited)
                elif step == 29:
                    with c.step(29, "일정 수정값 새로고침 영속성과 기존 일정 비변경"):
                        ids = {item.get("id") for item in _schedule_list(data, classroom_context.classroom_id, educator=True)}; educator.driver.refresh(); schedule.wait_until_loaded()
                        assert schedule.is_title_present_in_calendar(edited) and len(_schedule_matches(data, classroom_context.classroom_id, edited, educator=True)) == 1
                        assert {item.get("id") for item in _schedule_list(data, classroom_context.classroom_id, educator=True)} == ids
                elif step == 30:
                    with c.step(30, "일정 수정 후 취소 시 제목·시간 원본 유지"):
                        schedule.click_schedule_card_by_title(edited); schedule.click_edit_schedule(); schedule.fill_schedule_form(title=edited + "-취소")
                        schedule.cancel_schedule_form()
                        assert _schedule_matches(data, classroom_context.classroom_id, edited, educator=True) == [item]
                else:
                    with c.step(31, "일정 설명만 수정하고 제목·시각·ID 유지"):
                        description = f"{_QA_PREFIX} 설명-{uuid4().hex[:8]}"; schedule.open(); schedule.click_schedule_card_by_title(edited); schedule.click_edit_schedule()
                        _schedule_description(educator.driver, description); schedule.submit_schedule_form(); described = _schedule_matches(data, classroom_context.classroom_id, edited, educator=True)[0]
                        for field in ("id", "summary", "dt_start", "dt_end"): assert described.get(field) == item.get(field)
                        saved_description = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", described.get("description") or ""))).strip()
                        assert saved_description == description
            else:
                with c.step(32, "일정 삭제 확인창 취소 후 유지, 재삭제 확인 후 완전 제거"):
                    schedule.open(); schedule.click_schedule_card_by_title(title); schedule.click_delete_schedule(); assert _visible(educator.driver, By.CSS_SELECTOR, "[role='dialog'],.MuiDialog-paper")
                    schedule.cancel_delete(); assert len(_schedule_matches(data, classroom_context.classroom_id, title, educator=True)) == 1
                    schedule.click_schedule_card_by_title(title); schedule.click_delete_schedule(); schedule.confirm_delete()
                    assert not _schedule_matches(data, classroom_context.classroom_id, title, educator=True) and schedule.wait_title_disappears(title)
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_33_independent(
        self, request, integration_data: IntegrationData, educator_app_shell: AppShell,
        classroom_context: ClassroomContext, integration_cleanup: CleanupRegistry,
    ) -> None:
        """33번은 전용 반복 일정을 생성하거나 정책 차단을 확인하고 정리한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=33, end_step=33)
        data, educator = integration_data, educator_app_shell; schedule = ClassSchedulePage(educator); title = f"{_QA_PREFIX} 반복-{uuid4().hex[:8]}"
        try:
            with c.step(33, "제한된 반복 일정 저장 또는 명확한 정책 차단"):
                integration_cleanup.add(key="step33-recurrence", description="33단계 반복 일정 삭제", callback=lambda: _delete_schedules_by_title(data, classroom_context.classroom_id, title))
                schedule.open(); schedule.click_create_schedule_button(); schedule.fill_schedule_form(title=title, description="제한 반복 검증"); _schedule_times(educator.driver, data.schedule_start, data.schedule_end)
                _schedule_option(educator.driver, r"반복|repeat", True); dates = _visible(educator.driver, By.CSS_SELECTOR, "[role='dialog'] input[type='date'],.MuiPopover-paper input[type='date']")
                if len(dates) >= 3: _native(educator.driver, dates[-1], data.recurring_until.strftime("%Y-%m-%d"))
                schedule.submit_schedule_form()
                time.sleep(2); items = _schedule_matches(data, classroom_context.classroom_id, title, educator=True)
                if items: assert all(item.get("id") for item in items)
                else:
                    assert re.search(r"반복|지원|저장|기간|종료|사용할 수 없", _errors(educator.driver))
                    if schedule.is_form_open(): schedule.cancel_schedule_form()
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_35_independent(
        self, request, integration_data: IntegrationData, educator_app_shell: AppShell,
        classroom_context: ClassroomContext, integration_cleanup: CleanupRegistry,
    ) -> None:
        """35번은 전용 종일 일정을 생성하고 ID로 원복한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=35, end_step=35)
        data, educator = integration_data, educator_app_shell; schedule = ClassSchedulePage(educator); title = f"{_QA_PREFIX} 종일-{uuid4().hex[:8]}"
        try:
            with c.step(35, "종일 일정 생성과 날짜 경계·종일 표시 정확성"):
                start = data.all_day_date.replace(hour=0, minute=0, second=0, microsecond=0)
                created = _create_schedule(
                    schedule, data, classroom_context.classroom_id, title=title,
                    start=start, end=start + timedelta(days=1), description="종일 검증", all_day=True,
                )
                integration_cleanup.add(key="step35-all-day", description="35단계 종일 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, created["id"]))
                matches = _schedule_matches(data, classroom_context.classroom_id, title, educator=True); assert len(matches) == 1
                assert _is_all_day_schedule(matches[0])
                schedule.open(); assert schedule.is_title_present_in_calendar(title)
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_34_independent(
        self, request, integration_data: IntegrationData, educator_app_shell: AppShell,
        classroom_context: ClassroomContext, integration_cleanup: CleanupRegistry,
    ) -> None:
        """34번은 반복 생성/차단 결과를 이 테스트 안에서 재현한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=34, end_step=34)
        data, educator = integration_data, educator_app_shell; schedule = ClassSchedulePage(educator); title = f"{_QA_PREFIX} 반복-{uuid4().hex[:8]}"
        try:
            with c.step(34, "반복 규칙·인스턴스 또는 차단 결과의 캘린더/목록/상세/API 일치"):
                integration_cleanup.add(key="step34-recurrence", description="34단계 반복 일정 삭제", callback=lambda: _delete_schedules_by_title(data, classroom_context.classroom_id, title))
                schedule.open(); schedule.click_create_schedule_button(); schedule.fill_schedule_form(title=title, description="반복 일치 검증"); _schedule_times(educator.driver, data.schedule_start, data.schedule_end)
                _schedule_option(educator.driver, r"반복|repeat", True); dates = _visible(educator.driver, By.CSS_SELECTOR, "[role='dialog'] input[type='date'],.MuiPopover-paper input[type='date']")
                if len(dates) >= 3: _native(educator.driver, dates[-1], data.recurring_until.strftime("%Y-%m-%d"))
                schedule.submit_schedule_form()
                time.sleep(2); items = _schedule_matches(data, classroom_context.classroom_id, title, educator=True)
                if items:
                    for item in items:
                        assert item.get("summary") == title and datetime.fromisoformat(str(item["dt_start"]).replace("Z", "+00:00")).date() <= data.recurring_until.date()
                    schedule.open(); assert schedule.is_title_present_in_calendar(title); schedule.switch_to_list_view()
                    WebDriverWait(educator.driver, _SHORT_WAIT).until(lambda d: title in _body(d))
                else:
                    assert re.search(r"반복|지원|저장|기간|종료|사용할 수 없", _errors(educator.driver))
                    if schedule.is_form_open(): schedule.cancel_schedule_form()
        finally:
            integration_cleanup.run()
            c.write()


    @pytest.mark.parametrize("step", (36, 37))
    def test_excel_all_day_visibility_steps_independent(
        self, step: int, request, integration_data: IntegrationData, educator_app_shell: AppShell,
        learner_app_shell: AppShell, classroom_context: ClassroomContext, integration_cleanup: CleanupRegistry,
    ) -> None:
        """36~37번은 전용 종일 일정 하나를 생성하고 검증 뒤 삭제한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        data, educator, learner = integration_data, educator_app_shell, learner_app_shell; title = f"{_QA_PREFIX} 종일-{uuid4().hex[:8]}"
        educator_schedule = ClassSchedulePage(educator)
        try:
            start = data.all_day_date.replace(hour=0, minute=0, second=0, microsecond=0)
            created = _create_schedule(educator_schedule, data, classroom_context.classroom_id, title=title, start=start, end=start + timedelta(days=1), description="종일 검증", all_day=True)
            integration_cleanup.add(key=f"step{step}-all-day", description=f"{step}단계 종일 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, created["id"]))
            if step == 36:
                with c.step(36, "교육자 일정 생성·수정·삭제·보기 관리 UI 노출"):
                    educator_schedule.open(); assert educator_schedule.is_create_button_visible(); educator_schedule.click_schedule_card_by_title(title)
                    heading = next(e for e in _visible(educator.driver, By.CSS_SELECTOR, "h1,h2,h3,h4,h5,h6,[role='heading']") if e.text.strip() == title)
                    panel = educator.driver.execute_script("let n=arguments[0];while(n&&n!==document.body){if(n.querySelectorAll('button').length>=3)return n;n=n.parentElement;}return null;", heading)
                    detail_buttons = _visible(panel, By.CSS_SELECTOR, "button,[role='button']") if panel else []
                    assert len(detail_buttons) >= 3 and all(button.is_enabled() for button in detail_buttons[:2])
                    _close_schedule_detail(educator.driver, title); assert any(re.search(r"월|주|목록", accessible_name(e)) for e in _visible(educator.driver, By.CSS_SELECTOR, "button,[role='button']"))
            else:
                with c.step(37, "학습자 일정에서 교육자 생성 종일 일정 단일 표시·상세·목록 일치"):
                    schedule = ClassSchedulePage(learner); schedule.open()
                    WebDriverWait(learner.driver, _SHORT_WAIT).until(
                        lambda _: len(_schedule_matches(data, classroom_context.classroom_id, title, educator=False)) == 1
                    )
                    if not schedule.is_title_present_in_calendar(title, timeout=3):
                        learner.driver.refresh(); schedule.wait_until_loaded()
                    assert schedule.is_title_present_in_calendar(title, timeout=5)
                    schedule.click_schedule_card_by_title(title); _expect_schedule_detail_title(learner.driver, title); assert re.search(r"종일|하루", _body(learner.driver))
                    _close_schedule_detail(learner.driver, title); schedule.switch_to_list_view(); assert title in _body(learner.driver)
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_44_independent(
        self, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        e2e_settings: E2ESettings, classroom_context: ClassroomContext,
    ) -> None:
        """44번은 학습자 일정 관리 권한 차단만 단독 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=44, end_step=44)
        learner, data = learner_app_shell, integration_data; schedule = ClassSchedulePage(learner)
        try:
            with c.step(44, "학습자 일정 생성·수정·삭제 UI/관리 URL 차단 및 목록 불변"):
                schedule.open(); before = _stable_schedule_snapshot(data, classroom_context.classroom_id)
                assert not schedule.is_create_button_visible(timeout=3)
                labels = " ".join(accessible_name(e) for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='button']"))
                assert not re.search(r"일정\s*(만들기|추가|수정|삭제)", labels)
                admin_url = build_web_url(e2e_settings, f"/classrooms/{classroom_context.classroom_id}/schedules/manage")
                learner.driver.get(admin_url)
                time.sleep(1)
                body_text = _body(learner.driver)
                assert (
                    re.search(r"권한|접근.*불가|403|찾을 수 없|로그인", body_text)
                    or learner.driver.current_url != admin_url
                    or not schedule.is_create_button_visible(timeout=1)
                )
                assert _stable_schedule_snapshot(data, classroom_context.classroom_id) == before
        finally:
            c.write()


    def test_excel_step_43_independent(
        self, request, integration_data: IntegrationData, educator_app_shell: AppShell, learner_app_shell: AppShell,
        classroom_context: ClassroomContext, integration_cleanup: CleanupRegistry,
    ) -> None:
        """43번은 전용 종일/반복 일정의 학습자 공개 정책을 단독 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=43, end_step=43)
        data, educator, learner = integration_data, educator_app_shell, learner_app_shell
        title_all_day, title_recurrence = f"{_QA_PREFIX} 종일-{uuid4().hex[:8]}", f"{_QA_PREFIX} 반복-{uuid4().hex[:8]}"
        educator_schedule = ClassSchedulePage(educator)
        try:
            with c.step(43, "교육자 생성 종일·반복 일정의 학습자 공개 정책 일치"):
                start = data.all_day_date.replace(hour=0, minute=0, second=0, microsecond=0)
                created = _create_schedule(educator_schedule, data, classroom_context.classroom_id, title=title_all_day, start=start, end=start + timedelta(days=1), description="종일 공개 정책", all_day=True)
                integration_cleanup.add(key="step43-all-day", description="43단계 종일 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, created["id"]))
                integration_cleanup.add(key="step43-recurrence", description="43단계 반복 일정 삭제", callback=lambda: _delete_schedules_by_title(data, classroom_context.classroom_id, title_recurrence))
                educator_schedule.open(); educator_schedule.click_create_schedule_button(); educator_schedule.fill_schedule_form(title=title_recurrence, description="반복 공개 정책"); _schedule_times(educator.driver, data.schedule_start, data.schedule_end)
                _schedule_option(educator.driver, r"반복|repeat", True)
                educator_schedule.submit_schedule_form(); time.sleep(2)
                recurrence = _schedule_matches(data, classroom_context.classroom_id, title_recurrence, educator=True)
                if not recurrence and educator_schedule.is_form_open(): educator_schedule.cancel_schedule_form()
                learner_schedule = ClassSchedulePage(learner); learner_schedule.open()
                if not learner_schedule.is_title_present_in_calendar(title_all_day, timeout=_WAIT):
                    learner_schedule.reload()
                assert learner_schedule.is_title_present_in_calendar(title_all_day, timeout=_WAIT)
                assert len(_schedule_matches(data, classroom_context.classroom_id, title_all_day, educator=False)) == 1
                learner_recurrence = _schedule_matches(data, classroom_context.classroom_id, title_recurrence, educator=False)
                if recurrence: assert learner_recurrence and learner_schedule.is_title_present_in_calendar(title_recurrence)
                else: assert not learner_recurrence
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_38_independent(
        self, request, integration_data: IntegrationData, learner_app_shell: AppShell
    ) -> None:
        """38번은 빈 기간 이동 뒤 오늘 보기로 복귀하는 독립 검증이다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=38, end_step=38)
        schedule = ClassSchedulePage(learner_app_shell)
        try:
            with c.step(38, "데이터 없는 기간 이동·빈 상태·오늘 복귀"):
                schedule.open(); schedule.switch_to_calendar_view()
                for _ in range(integration_data.empty_period_moves): _schedule_move_period(learner_app_shell.driver, forward=True)
                for _ in range(12):
                    if schedule.is_empty_state_visible() or not _cards(schedule):
                        break
                    _schedule_move_period(learner_app_shell.driver, forward=True)
                assert schedule.is_empty_state_visible() or not _cards(schedule)
                assert not re.search(r"오류|에러|exception|500", _body(learner_app_shell.driver), re.I)
                schedule.go_to_today()
                WebDriverWait(learner_app_shell.driver, _SHORT_WAIT).until(lambda _: _today(learner_app_shell.driver))
        finally:
            try:
                schedule.go_to_today()
            except TimeoutException:
                pass
            c.write()

    def test_excel_step_39_independent(
        self, request, learner_app_shell: AppShell
    ) -> None:
        """39번은 보기/주말 토글 후 같은 기간과 오늘 상태를 확인한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=39, end_step=39)
        schedule = ClassSchedulePage(learner_app_shell)
        try:
            with c.step(39, "보기 단위 또는 주말 토글·이동·오늘 복귀 정확성"):
                schedule.open(); schedule.go_to_today(); period, cards = _period(learner_app_shell.driver), _cards(schedule)
                buttons = [e for e in role_elements(learner_app_shell.driver, "button", re.compile(r"월|주|목록|주말")) if e.is_displayed()]
                weekend_labels = [e for e in _visible(learner_app_shell.driver, By.TAG_NAME, "label") if "주말" in e.text]
                assert buttons or weekend_labels
                if weekend_labels or any("주말" in accessible_name(e) for e in buttons):
                    schedule.toggle_weekend(); toggled = _period(learner_app_shell.driver); schedule.toggle_weekend()
                else:
                    _switch_schedule_list(learner_app_shell.driver); toggled = _period(learner_app_shell.driver)
                assert toggled; _schedule_move_period(learner_app_shell.driver, forward=True); schedule.go_to_today()
                assert _period(learner_app_shell.driver) == period and _cards(schedule) == cards and _today(learner_app_shell.driver)
        finally:
            try:
                schedule.go_to_today()
            except TimeoutException:
                pass
            c.write()
    def test_excel_step_40_independent(
        self, request, integration_data: IntegrationData, learner_app_shell: AppShell, educator_app_shell: AppShell,
        classroom_context: ClassroomContext, integration_cleanup: CleanupRegistry,
    ) -> None:
        """40번은 전용 동일 날짜 일정을 만들어 API와 목록/상세를 대조한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=40, end_step=40)
        data, learner = integration_data, learner_app_shell; schedule = ClassSchedulePage(learner); educator_schedule = ClassSchedulePage(educator_app_shell)
        try:
            with c.step(40, "동일 날짜 복수 일정의 상세·목록 정렬·시간 일치"):
                titles = (f"{_QA_PREFIX} 동일일정-1-{uuid4().hex[:8]}", f"{_QA_PREFIX} 동일일정-2-{uuid4().hex[:8]}")
                first_start = datetime.now().astimezone().replace(second=0, microsecond=0) + timedelta(hours=2)
                first = _create_schedule(educator_schedule, data, classroom_context.classroom_id, title=titles[0], start=first_start, end=first_start + timedelta(minutes=30), description="동일 날짜 첫 일정")
                second = _create_schedule(educator_schedule, data, classroom_context.classroom_id, title=titles[1], start=first_start + timedelta(hours=1), end=first_start + timedelta(hours=1, minutes=30), description="동일 날짜 둘째 일정")
                integration_cleanup.add(key="step40-first", description="40단계 첫 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, first["id"]))
                integration_cleanup.add(key="step40-second", description="40단계 둘째 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, second["id"]))
                items = [item for item in _schedule_list(data, classroom_context.classroom_id, educator=False) if item.get("summary") in titles]
                assert {item.get("summary") for item in items} == set(titles)
                assert len({datetime.fromisoformat(str(item["dt_start"]).replace("Z", "+00:00")).date() for item in items}) == 1
                expected = tuple(item["summary"] for item in sorted(items, key=lambda item: item["dt_start"]))
                learner.driver.refresh(); schedule.open(); schedule.go_to_today(); schedule.switch_to_list_view()
                WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda d: all(title in _body(d) for title in expected)); body = _body(learner.driver)
                assert [body.index(title) for title in expected] == sorted(body.index(title) for title in expected)
                for item in items:
                    schedule.click_schedule_card_by_title(item["summary"]); _expect_schedule_detail_title(learner.driver, item["summary"])
                    local_start = datetime.fromisoformat(str(item["dt_start"]).replace("Z", "+00:00")).astimezone()
                    korean_time = f"{'오전' if local_start.hour < 12 else '오후'} {local_start.hour % 12 or 12}:{local_start:%M}"
                    detail_time = schedule.get_detail_time()
                    assert local_start.strftime("%H:%M") in detail_time or korean_time in detail_time; _close_schedule_detail(learner.driver, item["summary"])
        finally:
            try: schedule.go_to_today()
            except TimeoutException: pass
            integration_cleanup.run()
            c.write()


    @pytest.mark.parametrize("step", (41, 42))
    def test_excel_schedule_persistence_steps_independent(
        self, step: int, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        classroom_context: ClassroomContext,
    ) -> None:
        """41~42번은 새로고침/키보드 조작 뒤 일정 화면 상태를 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner, data = learner_app_shell, integration_data; schedule = ClassSchedulePage(learner)
        try:
            schedule.open()
            if step == 41:
                with c.step(41, "일정 새로고침·메뉴 왕복 후 로그인/기간/데이터 유지·중복 없음"):
                    schedule.switch_to_calendar_view()
                    period = _period(learner.driver)
                    before = _stable_schedule_snapshot(data, classroom_context.classroom_id)
                    learner.driver.refresh(); schedule.open(); schedule.switch_to_calendar_view()
                    assert _period(learner.driver) == period
                    assert _stable_schedule_snapshot(data, classroom_context.classroom_id) == before
                    BoardPage(learner).open(); schedule.open()
                    schedule.switch_to_calendar_view()
                    after = _stable_schedule_snapshot(data, classroom_context.classroom_id)
                    assert _period(learner.driver) == period and after == before
                    assert len({item[0] for item in after}) == len(after) and not re.search(r"로그인", learner.driver.current_url, re.I)
            else:
                with c.step(42, "일정 카드 키보드 Enter/Space 열기·닫기와 초점 복귀"):
                    matches = [e for e in text_elements(learner.driver, data.baseline_schedule_title, exact=False) if e.is_displayed()]; assert matches
                    card = _focus_activate(learner.driver, _ancestor(learner.driver, matches[-1])); _expect_schedule_detail_title(learner.driver, data.baseline_schedule_title)
                    heading = next(e for e in _visible(learner.driver, By.CSS_SELECTOR, "h1,h2,h3,h4,h5,h6,[role='heading']") if e.text.strip() == data.baseline_schedule_title)
                    panel = learner.driver.execute_script("let n=arguments[0];while(n&&n!==document.body){if(n.querySelectorAll(':scope button').length>=3)return n;n=n.parentElement;}return null;", heading)
                    close = _visible(panel, By.CSS_SELECTOR, "button")[-1]; _focus_activate(learner.driver, close); _focus_returned(learner.driver, card)
        finally:
            try:
                schedule.go_to_today()
            except TimeoutException:
                pass
            c.write()


    @pytest.mark.parametrize("step", (77, 78, 79, 80))
    def test_excel_schedule_navigation_steps_independent(
        self, step: int, request, learner_app_shell: AppShell
    ) -> None:
        """77~80번은 현재 일정 보기에서 이동·토글만 수행하고 오늘로 복귀한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        schedule = ClassSchedulePage(learner_app_shell)
        try:
            schedule.open(); schedule.go_to_today()
            if step == 77:
                with c.step(77, "일정 이전/다음 이동 후 오늘 복귀·현재 주/오늘 강조"):
                    period = _period(learner_app_shell.driver); _schedule_move_period(learner_app_shell.driver, forward=False); assert _period(learner_app_shell.driver) != period
                    _schedule_move_period(learner_app_shell.driver, forward=True); schedule.go_to_today(); assert _period(learner_app_shell.driver) == period and _today(learner_app_shell.driver)
            elif step == 78:
                with c.step(78, "일정 이전→다음 왕복 후 기간·카드·오늘 강조와 중복 없음"):
                    period, cards = _period(learner_app_shell.driver), _stable_schedule_cards(schedule)
                    _schedule_move_period(learner_app_shell.driver, forward=False); _schedule_move_period(learner_app_shell.driver, forward=True)
                    assert _period(learner_app_shell.driver) == period and _stable_schedule_cards(schedule) == cards
                    assert len(cards) == len(set(cards)) and _today(learner_app_shell.driver)
            elif step == 79:
                with c.step(79, "주말 끄기/켜기 전후 같은 기간·평일 일정 보존"):
                    period = _period(learner_app_shell.driver); before = tuple(e.get_attribute("data-date") for e in _visible(learner_app_shell.driver, By.CSS_SELECTOR, "[data-date]") if e.get_attribute("data-date"))
                    assert before; schedule.toggle_weekend(); assert _period(learner_app_shell.driver).split("|")[0].strip() == period.split("|")[0].strip()
                    hidden = tuple(e.get_attribute("data-date") for e in _visible(learner_app_shell.driver, By.CSS_SELECTOR, "[data-date]") if e.get_attribute("data-date")); assert set(hidden).issubset(set(before))
                    schedule.toggle_weekend(); assert tuple(e.get_attribute("data-date") for e in _visible(learner_app_shell.driver, By.CSS_SELECTOR, "[data-date]") if e.get_attribute("data-date")) == before
            else:
                with c.step(80, "지원하는 캘린더/목록 보기의 헤더·배치·정보 변화"):
                    calendar_signature = (
                        _period(learner_app_shell.driver),
                        len(_visible(learner_app_shell.driver, By.CSS_SELECTOR, "[data-date],th,[role='columnheader']")),
                        _cards(schedule),
                    )
                    assert calendar_signature[0] and calendar_signature[1] > 0
                    schedule.switch_to_list_view()
                    WebDriverWait(learner_app_shell.driver, _SHORT_WAIT).until(
                        lambda d: len(_visible(d, By.CSS_SELECTOR, "[data-date],th,[role='columnheader']")) != calendar_signature[1]
                        or _cards(schedule) != calendar_signature[2]
                    )
                    list_signature = (
                        _period(learner_app_shell.driver),
                        len(_visible(learner_app_shell.driver, By.CSS_SELECTOR, "[data-date],th,[role='columnheader']")),
                        _cards(schedule),
                    )
                    assert list_signature != calendar_signature and _body(learner_app_shell.driver)
        finally:
            try:
                schedule.go_to_today()
            except TimeoutException:
                pass
            c.write()


    @pytest.mark.parametrize("step", (81, 82, 83, 84))
    def test_excel_schedule_edge_steps_independent(
        self, step: int, request, integration_data: IntegrationData, learner_app_shell: AppShell
    ) -> None:
        """81~84번은 기준 일정만 사용하며 마지막에 오늘 보기로 복구한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner, data = learner_app_shell, integration_data; schedule = ClassSchedulePage(learner)
        try:
            # The service remembers the last selected view.  Force a known
            # calendar state before validating navigation or a list transition.
            schedule.open(); schedule.switch_to_calendar_view(); schedule.go_to_today()
            if step == 81:
                with c.step(81, "월 경계가 걸린 주의 날짜·월 라벨·일정 배치 정확성"):
                    dates = []
                    for _ in range(8):
                        values = [e.get_attribute("data-date") for e in _visible(learner.driver, By.CSS_SELECTOR, "[data-date]") if e.get_attribute("data-date")]
                        if len({v[:7] for v in values if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)}) >= 2: dates = values; break
                        _schedule_move_period(learner.driver, forward=True)
                    assert dates and all(value in learner.driver.page_source for value in set(dates)) and not re.search(r"NaN|Invalid Date", learner.driver.page_source)
            elif step == 82:
                with c.step(82, "빠른 이전/다음 연속 조작 후 최종 선택 기간만 표시"):
                    base = _period(learner.driver); _schedule_move_period(learner.driver, forward=True); expected = _period(learner.driver); schedule.go_to_today()
                    _schedule_move_period(learner.driver, forward=True); _schedule_move_period(learner.driver, forward=False); _schedule_move_period(learner.driver, forward=True)
                    WebDriverWait(learner.driver, _WAIT).until(lambda _: _period(learner.driver) == expected)
                    assert expected != base
            elif step == 83:
                with c.step(83, "일정 상세 열기/닫기 후 기간·보기·스크롤 위치 유지"):
                    period = _period(learner.driver); schedule.switch_to_list_view(); learner.driver.execute_script("window.scrollTo(0, 240)"); scroll = learner.driver.execute_script("return window.scrollY")
                    schedule.click_schedule_card_by_title(data.baseline_schedule_title); _expect_schedule_detail_title(learner.driver, data.baseline_schedule_title); _close_schedule_detail(learner.driver, data.baseline_schedule_title)
                    assert _period(learner.driver).split(" | ", 1)[0] == period.split(" | ", 1)[0] and learner.driver.execute_script("return window.scrollY") == scroll and data.baseline_schedule_title in _body(learner.driver)
            else:
                with c.step(84, "일정 카드 Tab 포커스·Enter/Space 실제 열기/닫기"):
                    matches = [e for e in text_elements(learner.driver, data.baseline_schedule_title, exact=False) if e.is_displayed()]
                    assert matches; card = _focus_activate(learner.driver, _ancestor(learner.driver, matches[-1]))
                    _expect_schedule_detail_title(learner.driver, data.baseline_schedule_title)
                    close = [
                        e for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='button']")
                        if re.search(r"닫기|close", accessible_name(e), re.I) and e.is_enabled()
                    ]
                    if not close:
                        heading = next(e for e in _visible(learner.driver, By.CSS_SELECTOR, "h1,h2,h3,h4,h5,h6,[role='heading']") if e.text.strip() == data.baseline_schedule_title)
                        panel = learner.driver.execute_script("let n=arguments[0];while(n&&n!==document.body){if(n.querySelectorAll('button').length>=1)return n;n=n.parentElement;}return null;", heading)
                        close = _visible(panel, By.CSS_SELECTOR, "button,[role='button']")[-1:]
                    assert close
                    learner.driver.execute_script("arguments[0].focus();", close[-1])
                    ActionChains(learner.driver).send_keys(Keys.SPACE).perform()
                    _focus_returned(learner.driver, card)
        finally:
            try:
                schedule.go_to_today()
            except TimeoutException:
                pass
            c.write()


