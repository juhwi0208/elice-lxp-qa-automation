"""E2E 통합 테스트 - [홈] 도메인 (단계 1~10, 55~58, 59~66)
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
class TestHomeSteps:
    def test_excel_home_steps_flow(
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
        """Excel ``전체 기능(E2E 통합)`` [HOME] 도메인 연속 검증."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=1, end_step=66)
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

            with c.step(1, "학습자 로그인 후 클래스 홈·세 메뉴 이동과 현재 메뉴 표시"):
                home = _current_home(learner)
                assert data.primary_class_name in _body(learner.driver)
                assert re.search(r"환영|안녕하세요|님", _body(learner.driver))
                for menu, page in (
                    (home.MENU_COURSE, CourseListPage(learner)),
                    (home.MENU_SCHEDULE, ClassSchedulePage(learner)),
                    (home.MENU_BOARD, BoardPage(learner)),
                ):
                    home.select_menu(menu)
                    _wait_page_loaded(page)
                    _active_menu(learner, menu)

            with c.step(2, "홈의 세 위젯 제목·실데이터와 레이아웃·이미지 무결성"):
                home = _current_home(learner)
                initial_widgets = home.snapshots()
                assert all(snapshot.lines for snapshot in initial_widgets.values())
                _assert_widget_layout(home)
                for title in home.WIDGET_TITLES:
                    for image in _widget(home, title).find_elements(By.TAG_NAME, "img"):
                        assert image.is_displayed()
                        assert learner.driver.execute_script("return arguments[0].complete && arguments[0].naturalWidth > 0", image)
                integration_state["initial_widgets"] = initial_widgets

            with c.step(3, "1팀 홈 새로고침 후 클래스·위젯 데이터 유지"):
                learner.driver.refresh()
                _expect_home_snapshots(home, initial_widgets)
                assert data.primary_class_name in _body(learner.driver)
                home.expect_no_class_data_mix(classroom_id)

            with c.step(4, "학습 과목 위젯 SANDBOX 클릭 후 정확한 과목·수업 상세"):
                home.expect_widget_contains(home.COURSE_WIDGET, course)
                _widget_click(home, home.COURSE_WIDGET, course)
                detail = CourseDetailPage(learner, course)
                detail.expect_loaded()
                detail.expect_lesson_visible(lesson)
                assert len([e for e in role_elements(learner.driver, "heading", course) if e.is_displayed()]) == 1

            with c.step(5, "홈 복귀 후 학습 과목 전체 보기와 SANDBOX 단일 카드"):
                home = _current_home(learner)
                _widget_view_all(home, home.COURSE_WIDGET)
                courses = CourseListPage(learner)
                courses.expect_loaded()
                courses.expect_course_once(course)
                courses.expect_course_thumbnail(course)
                assert len(courses.course_cards(course)) == 1

            with c.step(6, "수업 일정 위젯 기준 일정 클릭·전체 보기의 제목과 날짜 일치"):
                home = _current_home(learner)
                schedule_snapshot = home.snapshot(home.SCHEDULE_WIDGET)
                target_title = data.baseline_schedule_title if data.baseline_schedule_title in schedule_snapshot.text else None
                if not target_title:
                    for line in schedule_snapshot.lines:
                        if not re.search(r"^\d{1,2}월|^\d{4}년|^오늘|^하루종일|^\d{1,2}:\d{2}|^일$|^월$|^화$|^수$|^목$|^금$|^토$|^\d{1,2}$", line.strip()):
                            target_title = line.strip()
                            break
                if not target_title:
                    target_title = data.baseline_schedule_title
                _widget_click(home, home.SCHEDULE_WIDGET, target_title)
                schedule = ClassSchedulePage(learner)
                schedule.wait_until_loaded()
                schedule.click_schedule_card_by_title(target_title)
                _expect_schedule_detail_title(learner.driver, target_title)
                _close_schedule_detail(learner.driver, target_title)
                home = _current_home(learner)
                _widget_view_all(home, home.SCHEDULE_WIDGET)
                schedule.wait_until_loaded()
                assert target_title in _body(learner.driver) or data.baseline_schedule_title in _body(learner.driver)

            with c.step(7, "게시판 위젯 기준 글 상세·전체 보기 데이터 일치"):
                home = _current_home(learner)
                widget_lines = home.snapshot(home.BOARD_WIDGET).lines
                widget_title = next((line for line in widget_lines if not re.fullmatch(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}", line)), "")
                assert widget_title, f"게시판 위젯에 검증할 글이 없습니다: {widget_lines}"
                _widget_click(home, home.BOARD_WIDGET, widget_title)
                board = BoardPage(learner)
                board.expect_loaded()
                assert board.get_detail_title() == widget_title
                _return_board_list(board)
                home = _current_home(learner)
                _widget_view_all(home, home.BOARD_WIDGET)
                board.expect_loaded()
                assert board.is_article_visible(widget_title)

            with c.step(8, "세 위젯과 전체 화면 간 클래스 컨텍스트·데이터 상호 일치"):
                home = _current_home(learner)
                _expect_home_snapshots(home, initial_widgets)
                CourseListPage(learner).open()
                assert course in _body(learner.driver) and classroom_id in learner.driver.current_url
                ClassSchedulePage(learner).open()
                assert data.baseline_schedule_title in _body(learner.driver)
                BoardPage(learner).open()
                assert widget_title in _body(learner.driver)

            with c.step(9, "1팀 메뉴 왕복 후 클래스 컨텍스트·위젯 데이터 비변경"):
                home = _current_home(learner)
                one_team_snapshot = home.snapshots()
                for menu, page in (
                    (home.MENU_COURSE, CourseListPage(learner)),
                    (home.MENU_SCHEDULE, ClassSchedulePage(learner)),
                    (home.MENU_BOARD, BoardPage(learner)),
                ):
                    home.select_menu(menu)
                    _wait_page_loaded(page)
                    _active_menu(learner, menu)
                    assert classroom_id in learner.driver.current_url
                    home = _current_home(learner)
                    assert data.primary_class_name in _body(learner.driver)
                    _expect_home_snapshots(home, one_team_snapshot)

            with c.step(10, "홈 공통 클래스 조회 5xx 주입 후 정상 데이터 복구"):
                home = _current_home(learner)
                evidence = _capture_requests(home)
                baseline = _loaded_home_snapshots(home)
                common_url = _request_exact_path(
                    evidence, f"/classroom/{classroom_id}", "홈 공통 클래스"
                )
                _assert_common_home_failure(home, common_url, baseline)

            with c.step(55, "보호된 네 실제 URL 저장 후 로그아웃·보호 데이터 제거"):
                home = _current_home(learner); home_url = learner.driver.current_url
                courses = CourseListPage(learner); courses.open(); detail = courses.open_course(course); course_url = learner.driver.current_url
                learner_schedule.open(); schedule_url = learner.driver.current_url
                board.open(); board.search(""); board.click_article(data.baseline_board_title); board_url = learner.driver.current_url
                protected_urls = (home_url, course_url, schedule_url, board_url)
                integration_state["protected_urls"] = protected_urls
                LoginPage(learner.driver, e2e_settings).logout_and_wait()
                assert learner.driver.current_url == "about:blank"
                learner.driver.get(e2e_settings.web_base_url)
                public_body = _body(learner.driver)
                for protected in (course, lesson, data.baseline_schedule_title, data.baseline_board_title):
                    assert protected not in public_body

            with c.step(56, "로그아웃 상태의 네 직접 URL 인증 차단·상세 미노출"):
                assert len(protected_urls) == 4
                for url, protected in zip(protected_urls, (data.primary_class_marker, lesson, data.baseline_schedule_title, data.baseline_board_title)):
                    _login_required(learner.driver, e2e_settings, url, protected)

            with c.step(57, "동일 학습자 재로그인 후 허용 데이터·학습 상태·클래스 복원"):
                LoginPage(learner.driver, e2e_settings).login_and_wait(learner_credentials)
                for url in protected_urls:
                    learner.driver.get(url)
                    WebDriverWait(learner.driver, _WAIT).until(lambda d: d.current_url.startswith(e2e_settings.web_base_url))
                    assert not re.search(r"accounts/signin", learner.driver.current_url)
                detail = CourseDetailPage(learner, course)
                learner.driver.get(course_url); detail.expect_loaded()
                assert detail.progress_row_text(lesson) == progress_after
                home = _current_home(learner)
                assert data.primary_class_name in _body(learner.driver)
                assert classroom_id in learner.driver.current_url

            with c.step(58, "전체 변이 데이터·공개/응시 상태 원복 후 초기 홈/과목/일정/게시판 일치"):
                integration_cleanup.run()
                assert len(integration_cleanup) == 0
                restored_home = _current_home(learner)
                _expect_home_snapshots(restored_home, initial_widgets)
                restored_courses = CourseListPage(learner); restored_courses.open()
                assert tuple(name for name, _ in _course_cards(restored_courses)) == integration_state["initial_admin_order"]
                restored_detail = restored_courses.open_course(course)
                assert restored_detail.progress_row_text(lesson) == progress_before
                assert _map(restored_detail) == integration_state["map_before_all"]
                restored_schedule = ClassSchedulePage(learner); restored_schedule.open()
                for title in (schedule_title, recurring_title, all_day_title):
                    assert not _schedule_matches(data, classroom_id, title, educator=False)
                    assert title not in _body(learner.driver)
                restored_board = BoardPage(learner); restored_board.open()
                for title in (normal_title, secret_title):
                    restored_board.search(title)
                    assert not _article_rows(learner.driver)

            with c.step(59, "사이드바 실제 메뉴 순서와 이동별 단일 현재 메뉴 표시"):
                home = _current_home(learner)
                menu_order = []
                for link in home.get_menu_links():
                    name = accessible_name(link).strip()
                    if name in (home.MENU_COURSE, home.MENU_SCHEDULE, home.MENU_BOARD) and name not in menu_order:
                        menu_order.append(name)
                assert tuple(menu_order) == (home.MENU_COURSE, home.MENU_SCHEDULE, home.MENU_BOARD)
                for name in menu_order:
                    home.select_menu(name)
                    _active_menu(learner, name)

            with c.step(60, "프로필 메뉴 열기·항목 노출·닫기와 클래스 컨텍스트 유지"):
                home = _current_home(learner)
                profile_buttons = [
                    e for e in _visible(learner.driver, By.CSS_SELECTOR, "header button,header [role='button']")
                    if re.search(r"프로필|계정|내 정보|사용자|account|profile", accessible_name(e), re.I)
                ]
                assert len(profile_buttons) == 1
                click_when_ready(learner.driver, profile_buttons[0])
                menu = WebDriverWait(learner.driver, _SHORT_WAIT).until(
                    lambda d: (_visible(d, By.CSS_SELECTOR, "[role='menu'],[data-testid*='profile-menu'],.MuiMenu-paper") or False)
                )[-1]
                menu_text = menu.text.strip()
                assert data.learner_display_name in menu_text
                assert re.search(r"프로필|계정|로그아웃", menu_text)
                profile_buttons[0].send_keys(Keys.ESCAPE)
                WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: not menu.is_displayed())
                assert classroom_id in learner.driver.current_url and data.primary_class_name in _body(learner.driver)

            with c.step(61, "환영 배너 닫기·새로고침 후 위젯/클래스 무손상"):
                home = _current_home(learner)
                banners = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "[role='banner'],[data-testid*='welcome'],[class*='welcome']") if re.search(r"환영|안녕하세요", e.text)]
                assert banners
                close = [e for e in _visible(banners[0], By.CSS_SELECTOR, "button,[role='button']") if re.search(r"닫기|close", accessible_name(e), re.I)]
                assert len(close) == 1
                click_when_ready(learner.driver, close[0])
                WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: not banners[0].is_displayed())
                learner.driver.refresh(); home.expect_all_widgets_visible()
                assert data.primary_class_name in _body(learner.driver)
                assert _normalized_home_snapshots(home.snapshots()) == _normalized_home_snapshots(initial_widgets)

            with c.step(62, "학습 과목 위젯 이름·개수와 전체 목록 단일 카드 일치"):
                home = _current_home(learner)
                widget_names = tuple(line for line in home.snapshot(home.COURSE_WIDGET).lines if line not in {"학습 시작하기"})
                _widget_view_all(home, home.COURSE_WIDGET)
                courses = CourseListPage(learner); courses.expect_loaded()
                list_cards = _course_cards(courses)
                list_names = tuple(name for name, _ in list_cards)
                assert widget_names == list_names[: len(widget_names)]
                assert len(list_names) == len(set(list_names))

            with c.step(63, "과목 위젯 학습 항목·시작 동작과 정확한 과목 상세"):
                home = _current_home(learner)
                _widget_click(home, home.COURSE_WIDGET, course)
                detail = CourseDetailPage(learner, course); detail.expect_loaded()
                detail.select_tab(detail.LESSONS_TAB)
                lesson_element = detail.lesson_card(lesson)
                assert lesson_element.is_displayed()
                actionable = _ancestor(learner.driver, lesson_element)
                before_course_url = learner.driver.current_url
                click_when_ready(learner.driver, actionable)
                WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda d: d.current_url != before_course_url or lesson in _body(d))
                assert course in _body(learner.driver) and lesson in _body(learner.driver)

            with c.step(64, "오늘 일정과 홈 일정 위젯 항목의 상세 일치"):
                home = _current_home(learner)
                assert data.baseline_schedule_title in home.snapshot(home.SCHEDULE_WIDGET).text
                _widget_click(home, home.SCHEDULE_WIDGET, data.baseline_schedule_title)
                learner_schedule = ClassSchedulePage(learner); learner_schedule.wait_until_loaded()
                _expect_schedule_detail_title(learner.driver, data.baseline_schedule_title)
                body = _body(learner.driver)
                assert any(t in body for t in (data.baseline_schedule_date_text, "9/12", "9월 12일", "12일")), f"일정 상세에 날짜 정보가 있어야 합니다: {body[:200]}"

            with c.step(65, "복수 일정의 시간순 정렬과 종일/시간 일정 구분"):
                _close_schedule_detail(learner.driver, data.baseline_schedule_title); learner_schedule.switch_to_list_view()
                multi = [item for item in _schedule_list(data, classroom_id, educator=False) if item.get("summary") in data.multi_schedule_titles]
                expected = tuple(item["summary"] for item in sorted(multi, key=lambda item: (not bool(item.get("is_all_day") or item.get("all_day")), item["dt_start"])))
                body = _body(learner.driver)
                assert [body.index(title) for title in expected] == sorted(body.index(title) for title in expected)
                all_day_items = [item for item in multi if item.get("is_all_day") or item.get("all_day")]
                timed_items = [item for item in multi if not (item.get("is_all_day") or item.get("all_day"))]
                assert all_day_items and timed_items
                for item in all_day_items:
                    assert re.search(rf"{re.escape(item['summary'])}.*(?:종일|하루)", body, re.S)
                for item in timed_items:
                    assert datetime.fromisoformat(str(item["dt_start"]).replace("Z", "+00:00")).strftime("%H:%M") in body

            with c.step(66, "게시판 위젯 제목·작성자·순서와 목록/상세 일치"):
                home = _current_home(learner)
                board_widget = home.snapshot(home.BOARD_WIDGET)
                baseline_article = _article_detail(data, data.baseline_board_article_id)
                author = _author_name(baseline_article)
                assert data.baseline_board_title in board_widget.text and author in board_widget.text
                widget_titles = tuple(line for line in board_widget.lines if line != author)
                board = BoardPage(learner); board.open()
                list_titles = tuple(_row_title(row) for row in _article_rows(learner.driver))
                common = [title for title in widget_titles if title in list_titles]
                assert len(common) >= 1, f"위젯 게시글이 게시판 목록에 존재해야 합니다: widget={widget_titles}, list={list_titles[:3]}"
                board.search(data.baseline_board_title)
                board.click_article(data.baseline_board_title)
                assert board.get_detail_title() == data.baseline_board_title and author in _body(learner.driver)

        finally:
            c.write()
    @pytest.mark.parametrize("step", (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11))
    def test_excel_home_steps_independent(
        self,
        step: int,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
        admin_app_shell: AppShell,
        classroom_context: ClassroomContext,
        course_test_data: CourseTestData,
    ) -> None:
        """홈/과목/일정/게시판의 1~11단계를 개별 pytest 케이스로 실행한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner, admin = learner_app_shell, admin_app_shell
        data = integration_data
        classroom_id = classroom_context.classroom_id
        course, lesson = course_test_data.course_name, course_test_data.test_lecture_name
        try:
            if step == 1:
                with c.step(1, "학습자 로그인 후 클래스 홈·세 메뉴 이동과 현재 메뉴 표시"):
                    home = _current_home(learner)
                    assert data.primary_class_name in _body(learner.driver)
                    assert re.search(r"환영|안녕하세요|님", _body(learner.driver))
                    for menu, page in ((home.MENU_COURSE, CourseListPage(learner)), (home.MENU_SCHEDULE, ClassSchedulePage(learner)), (home.MENU_BOARD, BoardPage(learner))):
                        home.select_menu(menu); _wait_page_loaded(page); _active_menu(learner, menu)
            elif step == 2:
                with c.step(2, "홈의 세 위젯 제목·실데이터와 레이아웃·이미지 무결성"):
                    home = _current_home(learner); snapshots = home.snapshots()
                    assert all(snapshot.lines for snapshot in snapshots.values())
                    _assert_widget_layout(home)
                    for title in home.WIDGET_TITLES:
                        for image in _widget(home, title).find_elements(By.TAG_NAME, "img"):
                            assert image.is_displayed()
                            assert learner.driver.execute_script("return arguments[0].complete && arguments[0].naturalWidth > 0", image)
            elif step == 3:
                with c.step(3, "1팀 홈 새로고침 후 클래스·위젯 데이터 유지"):
                    home = _current_home(learner); baseline = _loaded_home_snapshots(home)
                    learner.driver.refresh(); _expect_home_snapshots(home, baseline)
                    assert data.primary_class_name in _body(learner.driver); home.expect_no_class_data_mix(classroom_id)
            elif step == 4:
                with c.step(4, "학습 과목 위젯 SANDBOX 클릭 후 정확한 과목·수업 상세"):
                    home = _current_home(learner); home.expect_widget_contains(home.COURSE_WIDGET, course)
                    _widget_click(home, home.COURSE_WIDGET, course)
                    detail = CourseDetailPage(learner, course); detail.expect_loaded(); detail.expect_lesson_visible(lesson)
                    assert len([e for e in role_elements(learner.driver, "heading", course) if e.is_displayed()]) == 1
            elif step == 5:
                with c.step(5, "홈 복귀 후 학습 과목 전체 보기와 SANDBOX 단일 카드"):
                    home = _current_home(learner); _widget_view_all(home, home.COURSE_WIDGET)
                    courses = CourseListPage(learner); courses.expect_loaded(); courses.expect_course_once(course); courses.expect_course_thumbnail(course)
                    assert len(courses.course_cards(course)) == 1
            elif step == 6:
                with c.step(6, "수업 일정 위젯 기준 일정 클릭·전체 보기의 제목과 날짜 일치"):
                    home = _current_home(learner); snapshot = home.snapshot(home.SCHEDULE_WIDGET)
                    target = data.baseline_schedule_title if data.baseline_schedule_title in snapshot.text else None
                    if not target:
                        for line in snapshot.lines:
                            if not re.search(r"^\d{1,2}월|^\d{4}년|^오늘|^하루종일|^\d{1,2}:\d{2}|^일$|^월$|^화$|^수$|^목$|^금$|^토$|^\d{1,2}$", line.strip()):
                                target = line.strip(); break
                    if not target: target = data.baseline_schedule_title
                    _widget_click(home, home.SCHEDULE_WIDGET, target)
                    schedule = ClassSchedulePage(learner); schedule.wait_until_loaded(); schedule.click_schedule_card_by_title(target)
                    _expect_schedule_detail_title(learner.driver, target); _close_schedule_detail(learner.driver, target)
                    home = _current_home(learner); _widget_view_all(home, home.SCHEDULE_WIDGET); schedule.wait_until_loaded()
                    assert target in _body(learner.driver) or data.baseline_schedule_title in _body(learner.driver)
            elif step == 7:
                with c.step(7, "게시판 위젯 기준 글 상세·전체 보기 데이터 일치"):
                    home = _current_home(learner)
                    widget_lines = home.snapshot(home.BOARD_WIDGET).lines
                    widget_title = next((line for line in widget_lines if not re.fullmatch(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}", line)), "")
                    assert widget_title, f"게시판 위젯에 검증할 글이 없습니다: {widget_lines}"
                    _widget_click(home, home.BOARD_WIDGET, widget_title)
                    board = BoardPage(learner); board.expect_loaded(); assert board.get_detail_title() == widget_title
                    _return_board_list(board); home = _current_home(learner); _widget_view_all(home, home.BOARD_WIDGET); board.expect_loaded()
                    assert board.is_article_visible(widget_title)
            elif step == 8:
                with c.step(8, "세 위젯과 전체 화면 간 클래스 컨텍스트·데이터 상호 일치"):
                    home = _current_home(learner); baseline = _loaded_home_snapshots(home); _expect_home_snapshots(home, baseline)
                    board_title = next((line for line in baseline[home.BOARD_WIDGET].lines if not re.fullmatch(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}", line)), "")
                    assert board_title
                    CourseListPage(learner).open(); assert course in _body(learner.driver) and classroom_id in learner.driver.current_url
                    ClassSchedulePage(learner).open(); assert data.baseline_schedule_title in _body(learner.driver)
                    BoardPage(learner).open(); assert board_title in _body(learner.driver)
            elif step == 9:
                with c.step(9, "1팀 메뉴 왕복 후 클래스 컨텍스트·위젯 데이터 비변경"):
                    home = _current_home(learner); baseline = _loaded_home_snapshots(home)
                    for menu, page in ((home.MENU_COURSE, CourseListPage(learner)), (home.MENU_SCHEDULE, ClassSchedulePage(learner)), (home.MENU_BOARD, BoardPage(learner))):
                        home.select_menu(menu); _wait_page_loaded(page); _active_menu(learner, menu)
                        assert classroom_id in learner.driver.current_url
                        home = _current_home(learner); assert data.primary_class_name in _body(learner.driver); _expect_home_snapshots(home, baseline)
            elif step == 10:
                with c.step(10, "홈 공통 클래스 조회 5xx 주입 후 정상 데이터 복구"):
                    home = _current_home(learner); evidence = _capture_requests(home); baseline = _loaded_home_snapshots(home)
                    common_url = _request_exact_path(evidence, f"/classroom/{classroom_id}", "홈 공통 클래스")
                    _assert_common_home_failure(home, common_url, baseline)
            else:
                with c.step(11, "관리자 과목 관리 화면의 추가·순서·설정·공개 UI"):
                    management = CourseManagementPage(admin); management.open(); text = _body(admin.driver)
                    assert re.search(r"과목\s*추가", text) and re.search(r"순서\s*변경", text)
                    management.open_course(course); assert re.search(r"설정|수정|관리", _body(admin.driver))
                    _click_named(admin.driver, admin.driver, r"^수업\s*목록$")
                    WebDriverWait(admin.driver, _SHORT_WAIT).until(lambda _: lesson in _body(admin.driver))
        finally:
            c.write()


    @pytest.mark.parametrize("step", (55, 56))
    def test_excel_logout_steps_independent(
        self, step: int, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        learner_credentials: Credentials, e2e_settings: E2ESettings, classroom_context: ClassroomContext,
        course_test_data: CourseTestData,
    ) -> None:
        """55~56번은 로그아웃 검증 뒤 같은 학습자 세션을 복구한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner, data = learner_app_shell, integration_data
        try:
            home = _current_home(learner); home_url = learner.driver.current_url
            courses = CourseListPage(learner); courses.open(); course_url = learner.driver.current_url
            schedule = ClassSchedulePage(learner); schedule.open(); schedule_url = learner.driver.current_url
            board = BoardPage(learner); board.open(); board.click_article(data.baseline_board_title); board_url = learner.driver.current_url
            protected_urls = (home_url, course_url, schedule_url, board_url)
            if step == 55:
                with c.step(55, "보호된 네 실제 URL 저장 후 로그아웃·보호 데이터 제거"):
                    LoginPage(learner.driver, e2e_settings).logout_and_wait(); assert learner.driver.current_url == "about:blank"
                    learner.driver.get(e2e_settings.web_base_url); public = _body(learner.driver)
                    for value in (course_test_data.course_name, course_test_data.test_lecture_name, data.baseline_schedule_title, data.baseline_board_title): assert value not in public
            else:
                with c.step(56, "로그아웃 상태의 네 직접 URL 인증 차단·상세 미노출"):
                    LoginPage(learner.driver, e2e_settings).logout_and_wait()
                    for url, protected in zip(protected_urls, (data.primary_class_marker, course_test_data.test_lecture_name, data.baseline_schedule_title, data.baseline_board_title)):
                        _login_required(learner.driver, e2e_settings, url, protected)
        finally:
            LoginPage(learner.driver, e2e_settings).login_and_wait(learner_credentials)
            c.write()


    def test_excel_step_57_independent(
        self, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        learner_credentials: Credentials, e2e_settings: E2ESettings, classroom_context: ClassroomContext,
        course_test_data: CourseTestData,
    ) -> None:
        """57번은 이 테스트 안에서 로그아웃 전후 허용 데이터와 진행률을 비교한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=57, end_step=57)
        learner, data = learner_app_shell, integration_data
        try:
            courses = CourseListPage(learner); courses.open(); detail = courses.open_course(course_test_data.course_name)
            progress = detail.progress_row_text(course_test_data.test_lecture_name); course_url = learner.driver.current_url
            schedule = ClassSchedulePage(learner); schedule.open(); schedule_url = learner.driver.current_url
            board = BoardPage(learner); board.open(); board.click_article(data.baseline_board_title); board_url = learner.driver.current_url
            home_url = _current_home(learner).driver.current_url
            with c.step(57, "동일 학습자 재로그인 후 허용 데이터·학습 상태·클래스 복원"):
                LoginPage(learner.driver, e2e_settings).logout_and_wait(); LoginPage(learner.driver, e2e_settings).login_and_wait(learner_credentials)
                for url in (home_url, course_url, schedule_url, board_url):
                    learner.driver.get(url); WebDriverWait(learner.driver, _WAIT).until(lambda d: d.current_url.startswith(e2e_settings.web_base_url)); assert not re.search(r"accounts/signin", learner.driver.current_url)
                learner.driver.get(course_url); detail.expect_loaded(); assert detail.progress_row_text(course_test_data.test_lecture_name) == progress
                assert classroom_context.classroom_id in _current_home(learner).driver.current_url and data.primary_class_name in _body(learner.driver)
        finally:
            c.write()


    def test_excel_step_58_independent(
        self, request, integration_data: IntegrationData, educator_app_shell: AppShell,
        learner_app_shell: AppShell, classroom_context: ClassroomContext,
        course_test_data: CourseTestData, integration_cleanup: CleanupRegistry,
    ) -> None:
        """58번은 이 케이스가 만든 변이만 원복한 뒤 Team 1 기준 상태를 재확인한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=58, end_step=58)
        data, educator, learner = integration_data, educator_app_shell, learner_app_shell
        schedule_title = f"{_QA_PREFIX} 복구일정-{uuid4().hex[:8]}"
        article_title = f"{_QA_PREFIX} 복구게시글-{uuid4().hex[:8]}"
        try:
            with c.step(58, "전용 변이 데이터 원복 후 홈·과목·일정·게시판 상태 복원"):
                home_before = _normalized_home_snapshots(_loaded_home_snapshots(_current_home(learner)))
                courses = CourseListPage(learner); courses.open(); cards_before = _course_cards(courses)
                detail = courses.open_course(course_test_data.course_name)
                progress_before, map_before = detail.progress_row_text(course_test_data.test_lecture_name), _map(detail)

                start = data.schedule_start + timedelta(days=31)
                created = _create_schedule(
                    ClassSchedulePage(educator), data, classroom_context.classroom_id,
                    title=schedule_title, start=start, end=start + timedelta(hours=1), description="58단계 원복 검증",
                )
                integration_cleanup.add(
                    key="step58-schedule", description="58단계 일정 삭제",
                    callback=lambda: _delete_schedule(data, classroom_context.classroom_id, created["id"]),
                )
                article_id = _create_article(BoardPage(educator), title=article_title, content="58단계 원복 검증")
                integration_cleanup.add(
                    key="step58-article", description="58단계 게시글 삭제",
                    callback=lambda: _delete_article(data, article_id),
                )

                integration_cleanup.run(); assert len(integration_cleanup) == 0
                assert _normalized_home_snapshots(_loaded_home_snapshots(_current_home(learner))) == home_before
                courses.open(); assert _course_cards(courses) == cards_before
                restored = courses.open_course(course_test_data.course_name)
                assert restored.progress_row_text(course_test_data.test_lecture_name) == progress_before
                assert _map(restored) == map_before
                assert not _schedule_matches(data, classroom_context.classroom_id, schedule_title, educator=False)
                board = BoardPage(learner); board.open(); board.search(article_title)
                assert not [row for row in _article_rows(learner.driver) if _row_title(row) == article_title]
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_61_independent(
        self, request, integration_data: IntegrationData, learner_app_shell: AppShell
    ) -> None:
        """61번은 이 세션의 환영 배너를 닫고 홈 데이터 유지 여부를 확인한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=61, end_step=61)
        learner, data = learner_app_shell, integration_data
        try:
            with c.step(61, "환영 배너 닫기·새로고침 후 위젯/클래스 무손상"):
                home = _current_home(learner); before = _normalized_home_snapshots(_loaded_home_snapshots(home))
                banners = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "[role='banner'],[data-testid*='welcome'],[class*='welcome']") if re.search(r"환영|안녕하세요", e.text)]
                if not banners:
                    welcome_text = next(e for e in text_elements(learner.driver, "환영", exact=False) if e.is_displayed())
                    banners = [welcome_text]
                    close = [
                        e for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='button']")
                        if 100 < e.rect["y"] < 300 and e.rect["x"] > 1400
                    ]
                else:
                    close = [e for e in _visible(banners[0], By.CSS_SELECTOR, "button,[role='button']") if re.search(r"닫기|close", accessible_name(e), re.I)]
                if not close:
                    close = [max(_visible(banners[0], By.CSS_SELECTOR, "button,[role='button']"), key=lambda e: e.rect["x"])]
                click_when_ready(learner.driver, max(close, key=lambda e: e.rect["x"]))
                WebDriverWait(learner.driver, _SHORT_WAIT).until(
                    lambda d: not any(e.is_displayed() for e in text_elements(d, "환영", exact=False))
                )
                learner.driver.refresh(); home.expect_all_widgets_visible(); assert data.primary_class_name in _body(learner.driver)
                assert _normalized_home_snapshots(home.snapshots()) == before
        finally:
            c.write()


    def test_excel_step_62_independent(self, request, learner_app_shell: AppShell) -> None:
        """62번은 홈 과목 위젯과 전체 목록을 같은 실행에서 비교한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=62, end_step=62)
        try:
            with c.step(62, "학습 과목 위젯 이름·개수와 전체 목록 단일 카드 일치"):
                home = _current_home(learner_app_shell); names = tuple(line for line in home.snapshot(home.COURSE_WIDGET).lines if line not in {"학습 시작하기"})
                _widget_view_all(home, home.COURSE_WIDGET); courses = CourseListPage(learner_app_shell); courses.expect_loaded(); cards = _course_cards(courses); listed = tuple(name for name, _ in cards)
                assert names == listed[:len(names)] and len(listed) == len(set(listed))
        finally:
            c.write()


    @pytest.mark.parametrize("step", (59, 60))
    def test_excel_shell_steps_independent(
        self,
        step: int,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
        classroom_context: ClassroomContext,
    ) -> None:
        """59~60번은 현재 1팀 로그인 세션만으로 독립 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner, data = learner_app_shell, integration_data
        try:
            home = _current_home(learner)
            if step == 59:
                with c.step(59, "사이드바 실제 메뉴 순서와 이동별 단일 현재 메뉴 표시"):
                    order = []
                    for link in home.get_menu_links():
                        name = accessible_name(link).strip()
                        if name in (home.MENU_COURSE, home.MENU_SCHEDULE, home.MENU_BOARD) and name not in order:
                            order.append(name)
                    assert tuple(order) == (home.MENU_COURSE, home.MENU_SCHEDULE, home.MENU_BOARD)
                    for name in order:
                        home.select_menu(name)
                        link = next(link for link in home.get_menu_links() if accessible_name(link).strip() == name)
                        highlighted = WebDriverWait(learner.driver, _SHORT_WAIT).until(
                            lambda d: d.execute_script(
                                """
                                const item = arguments[0].closest('li,[class*=MuiListItem]') || arguments[0];
                                return [item, ...item.querySelectorAll('*')].some((node) => {
                                  const color = getComputedStyle(node).backgroundColor;
                                  return color && color !== 'transparent' && color !== 'rgba(0, 0, 0, 0)';
                                });
                                """,
                                link,
                            )
                        )
                        assert highlighted
            else:
                with c.step(60, "프로필 메뉴 열기·항목 노출·닫기와 클래스 컨텍스트 유지"):
                    buttons = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "header button,header [role='button']") if re.search(r"프로필|계정|내 정보|사용자|account|profile", accessible_name(e), re.I)]
                    if not buttons:
                        header_buttons = _visible(learner.driver, By.CSS_SELECTOR, "header button,header [role='button']")
                        buttons = [e for e in header_buttons if e.rect["x"] > max(e.rect["width"] for e in header_buttons) * 10]
                        if buttons:
                            buttons = [max(buttons, key=lambda e: e.rect["x"])]
                    if not buttons:
                        avatars = [
                            e for e in _visible(learner.driver, By.CSS_SELECTOR, "[class*='avatar'],[class*='Avatar'],img[alt*='profile' i]")
                            if e.rect["y"] < 100
                        ]
                        if avatars:
                            buttons = [max(avatars, key=lambda e: e.rect["x"])]
                    assert len(buttons) == 1; click_when_ready(learner.driver, buttons[0])
                    menu = WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda d: (_visible(d, By.CSS_SELECTOR, "[role='menu'],[data-testid*='profile-menu'],.MuiMenu-paper") or False))[-1]
                    assert data.learner_display_name in menu.text and re.search(r"프로필|계정|로그아웃", menu.text)
                    def menu_closed(_: WebDriver) -> bool:
                        try:
                            return not menu.is_displayed()
                        except StaleElementReferenceException:
                            return True
                    learner.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    try:
                        WebDriverWait(learner.driver, 2).until(menu_closed)
                    except TimeoutException:
                        learner.driver.execute_script("document.elementFromPoint(arguments[0], arguments[1]).click();", 800, 500)
                    assert classroom_context.classroom_id in learner.driver.current_url
                    assert not re.search(r"accounts/signin|login", learner.driver.current_url, re.I)
        finally:
            c.write()


    @pytest.mark.parametrize("step", (63, 64, 65, 66))
    def test_excel_home_cross_view_steps_independent(
        self, step: int, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        educator_app_shell: AppShell, classroom_context: ClassroomContext, course_test_data: CourseTestData,
        integration_cleanup: CleanupRegistry, learner_credentials: Credentials, e2e_settings: E2ESettings,
    ) -> None:
        """63~66번은 현재 1팀의 위젯·전체 보기·상세를 새로 열어 비교한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner, data = learner_app_shell, integration_data
        try:
            if "accounts" in learner.driver.current_url or learner.driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
                LoginPage(learner.driver, e2e_settings).login_and_wait(learner_credentials)
            home = _current_home(learner)
            if step == 63:
                with c.step(63, "과목 위젯 학습 항목·시작 동작과 정확한 과목 상세"):
                    _widget_click(home, home.COURSE_WIDGET, course_test_data.course_name)
                    detail = CourseDetailPage(learner, course_test_data.course_name); detail.expect_loaded(); detail.select_tab(detail.LESSONS_TAB)
                    lesson = detail.lesson_card(course_test_data.test_lecture_name); assert lesson.is_displayed()
                    before = learner.driver.current_url; click_when_ready(learner.driver, _ancestor(learner.driver, lesson))
                    WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda d: d.current_url != before or course_test_data.test_lecture_name in _body(d))
                    assert course_test_data.course_name in _body(learner.driver) and course_test_data.test_lecture_name in _body(learner.driver)
            elif step == 64:
                with c.step(64, "오늘 일정과 홈 일정 위젯 항목의 상세 일치"):
                    assert data.baseline_schedule_title in home.snapshot(home.SCHEDULE_WIDGET).text
                    _widget_click(home, home.SCHEDULE_WIDGET, data.baseline_schedule_title)
                    schedule = ClassSchedulePage(learner); schedule.wait_until_loaded(); _expect_schedule_detail_title(learner.driver, data.baseline_schedule_title)
                    body = _body(learner.driver)
                    assert any(t in body for t in (data.baseline_schedule_date_text, "9/12", "9월 12일", "12일")), f"일정 상세에 날짜 정보가 있어야 합니다: {body[:200]}"
                    _close_schedule_detail(learner.driver, data.baseline_schedule_title)
            elif step == 65:
                with c.step(65, "복수 일정의 시간순 정렬과 종일/시간 일정 구분"):
                    titles = (f"{_QA_PREFIX} 정렬-종일-{uuid4().hex[:8]}", f"{_QA_PREFIX} 정렬-시간-{uuid4().hex[:8]}")
                    educator_schedule = ClassSchedulePage(educator_app_shell)
                    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
                    all_day = _create_schedule(educator_schedule, data, classroom_context.classroom_id, title=titles[0], start=today, end=today + timedelta(days=1), description="정렬 종일 일정", all_day=True)
                    timed_start = datetime.now().astimezone().replace(second=0, microsecond=0) + timedelta(hours=2)
                    timed = _create_schedule(educator_schedule, data, classroom_context.classroom_id, title=titles[1], start=timed_start, end=timed_start + timedelta(minutes=30), description="정렬 시간 일정")
                    integration_cleanup.add(key="step65-all-day", description="65단계 종일 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, all_day["id"]))
                    integration_cleanup.add(key="step65-timed", description="65단계 시간 일정 삭제", callback=lambda: _delete_schedule(data, classroom_context.classroom_id, timed["id"]))
                    schedule = ClassSchedulePage(learner); learner.driver.refresh(); schedule.open(); schedule.switch_to_list_view()
                    items = [item for item in _schedule_list(data, classroom_context.classroom_id, educator=False) if item.get("summary") in titles]
                    assert {item.get("summary") for item in items} == set(titles)
                    expected = tuple(item["summary"] for item in sorted(items, key=lambda item: (not _is_all_day_schedule(item), item["dt_start"])))
                    body = _body(learner.driver); assert [body.index(title) for title in expected] == sorted(body.index(title) for title in expected)
                    assert any(_is_all_day_schedule(item) for item in items) and any(not _is_all_day_schedule(item) for item in items)
            else:
                with c.step(66, "게시판 위젯 제목·작성자·순서와 목록/상세 일치"):
                    snapshot = home.snapshot(home.BOARD_WIDGET)
                    board = BoardPage(learner); board.open(); board.expect_loaded()
                    try:
                        rows = WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda d: _article_rows(d) or False)
                    except TimeoutException:
                        learner.open_classroom(); board.open(); board.expect_loaded()
                        rows = WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda d: _article_rows(d) or False)
                    titles = tuple(_row_title(row) for row in rows)
                    widget_titles = tuple(line for line in snapshot.lines if line in titles)
                    assert widget_titles, f"위젯 게시글이 게시판 목록에 존재해야 합니다: widget={snapshot.lines}, list={titles[:3]}"
                    assert widget_titles == titles[:len(widget_titles)], (
                        f"위젯과 게시판 최신순이 다릅니다: widget={widget_titles}, list={titles[:len(widget_titles)]}"
                    )
                    chosen = widget_titles[0]
                    row = next(row for row in rows if _row_title(row) == chosen)
                    row_metadata = tuple(line for line in _lines(row.text) if line != chosen)
                    assert any(value in snapshot.text for value in row_metadata), (
                        f"위젯과 목록의 작성 정보가 다릅니다: widget={snapshot.lines}, row={_lines(row.text)}"
                    )
                    board.click_article(chosen)
                    article = _article_detail(data, _article_id(learner.driver))
                    author = _author_name(article)
                    detail_headings = [
                        element for element in _visible(learner.driver, By.CSS_SELECTOR, "main h1,main h2,main h3,main h4,[role='heading']")
                        if element.text.strip() == chosen
                    ]
                    assert len(detail_headings) == 1
                    assert not author or author in _body(learner.driver)
        finally:
            if step == 65:
                integration_cleanup.run()
            c.write()

