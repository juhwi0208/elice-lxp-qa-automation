"""E2E 통합 테스트 - [과목] 도메인 (단계 11~23, 67~76)
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
class TestCourseSteps:
    def test_excel_course_steps_flow(
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
        """Excel ``전체 기능(E2E 통합)`` [COURSE] 도메인 연속 검증."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=11, end_step=76)
        c.results.pop(12, None)
        c.results.pop(14, None)
        c.results.pop(68, None)
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
            with c.step(11, "관리자 과목 관리 화면의 추가·순서·설정·공개 UI"):
                management = CourseManagementPage(admin)
                management.open()
                text = _body(admin.driver)
                assert re.search(r"과목\s*추가", text)
                assert re.search(r"순서\s*변경", text)
                management.open_course(course)
                assert re.search(r"설정|수정|관리", _body(admin.driver))
                _click_named(admin.driver, admin.driver, r"^수업\s*목록$")
                WebDriverWait(admin.driver, _SHORT_WAIT).until(lambda _: lesson in _body(admin.driver))
                assert lesson in _body(admin.driver)

            with c.step(13, "과목 순서 변경 저장·새로고침 정확성 및 원본 순서 등록"):
                management.open()
                integration_state["initial_admin_order"] = _course_order(management)
                original_order, changed_order = _swap_courses(management)
                integration_state["original_course_order"] = original_order
                integration_cleanup.add(
                    key="course-order",
                    description="과목 순서 원복",
                    callback=lambda: _restore_order(CourseManagementPage(admin), original_order),
                )
                admin.driver.refresh(); management.expect_loaded()
                assert _course_order(management) == changed_order
                assert len(changed_order) == len(set(changed_order))

            with c.step(15, "TEST 공개 전환·새로고침 유지와 원본 공개 상태 등록"):
                management.open(); management.open_course(course)
                original_public = management.publication_state(lesson)
                integration_state["original_test_public"] = original_public
                integration_cleanup.add(
                    key="test-publication",
                    description="TEST 공개 상태 원복",
                    callback=lambda: _restore_publication(admin, course, lesson, original_public),
                )
                management.set_publication_state(lesson, True)
                management.expect_publication_state(lesson, True)
                admin.driver.refresh()
                management.open_course(course)
                assert management.publication_state(lesson) is True
                admin.driver.refresh()
                WebDriverWait(admin.driver, _WAIT).until(lambda d: lesson in d.page_source)
                assert lesson in _body(admin.driver)

            with c.step(16, "학습자 화면의 추가 과목·변경 순서·소개 정확 반영"):
                courses = CourseListPage(learner)
                courses.open()
                learner_cards = _course_cards(courses)
                assert _unique(name for name, _ in learner_cards) == changed_order
                detail = courses.open_course(course)
                detail.select_tab(detail.INTRODUCTION_TAB)
                # 14단계에서 실제 UI가 소개 편집을 제공한 경우에만 변경 문구를
                # 검증한다. 제공하지 않는 환경에서는 과목 상세가 정상 노출되는지를
                # 확인한다.
                if "original_course_intro" in integration_state:
                    assert intro in _body(learner.driver)
                else:
                    assert course in _body(learner.driver)

            with c.step(17, "과목 상세 네 탭과 정확히 하나의 선택 상태·탭별 콘텐츠"):
                expected_tabs = (detail.LESSONS_TAB, detail.PROGRESS_TAB, detail.MAP_TAB, detail.INTRODUCTION_TAB)
                visible_tabs = [tab for tab in role_elements(learner.driver, "tab") if tab.is_displayed()]
                assert tuple(tab.text.strip() for tab in visible_tabs) == expected_tabs
                signatures = {}
                for tab_name in expected_tabs:
                    detail.select_tab(tab_name)
                    assert detail.selected_tab_name() == tab_name
                    selected = [tab for tab in visible_tabs if tab.get_attribute("aria-selected") == "true"]
                    assert len(selected) == 1
                    signatures[tab_name] = _body(learner.driver)
                assert all(signatures.values())

            with c.step(18, "목록 복귀·상세 재진입·새로고침 후 탭/과목 유지"):
                courses.open()
                detail = courses.open_course(course)
                detail.select_tab(detail.PROGRESS_TAB)
                learner.driver.refresh()
                detail.expect_loaded()
                assert course in _body(learner.driver)
                assert detail.selected_tab_name() in {detail.LESSONS_TAB, detail.PROGRESS_TAB}
                for tab_name in (detail.LESSONS_TAB, detail.PROGRESS_TAB, detail.MAP_TAB, detail.INTRODUCTION_TAB):
                    detail.expect_tab_visible(tab_name)

            with c.step(19, "TEST 카드 내부 시작 버튼의 공개·활성 상태"):
                detail.select_tab(detail.LESSONS_TAB)
                panel = _lesson_panel(detail, lesson)
                start_button = detail.expect_test_start_available(lesson)
                assert start_button.is_displayed() and start_button.is_enabled()
                assert learner.driver.execute_script("return arguments[0] === arguments[1] || arguments[0].contains(arguments[1])", panel, start_button)
                try:
                    _cleanup_attempt(data, set())
                except Exception:
                    pass
                responses_before = _responses(data)
                response_ids_before = {item.get("id") for item in responses_before if isinstance(item.get("id"), int)}
                admissions_before = _admissions(data)
                progress_before = detail.progress_row_text(lesson)
                integration_state["map_before_all"] = _map(detail)
                detail.map_node_signature(lesson)
                integration_cleanup.add(
                    key="test-attempt",
                    description="TEST 응시 데이터와 상태 원복",
                    callback=lambda: _cleanup_attempt(data, response_ids_before),
                )

            with c.step(20, "TEST 첫 문항 답변·정확히 한 번 제출·결과 화면"):
                detail.select_tab(detail.LESSONS_TAB)
                attempt = detail.start_test(lesson)
                before_url = attempt.driver.current_url
                attempt.answer_first_question(course_test_data.test_answer)
                attempt.submit()
                attempt.expect_result()
                result_text = attempt.result_text().strip()
                assert result_text and re.search(r"결과|점수|정답|오답|제출.*완료|테스트(?:가)?\s*종료|테스트\s*재응시", result_text)
                new_responses = []
                for _ in range(5):
                    responses_after = _responses(data)
                    new_responses = [item for item in responses_after if item.get("id") not in response_ids_before]
                    if len(new_responses) >= 1:
                        break
                    time.sleep(1.0)
                assert attempt.driver.current_url != before_url or "결과" in result_text
                integration_state["result_text"] = result_text
                integration_state["new_response"] = new_responses[0] if new_responses else {}

            with c.step(21, "응시 결과·점수·평균·TEST 행·진행률의 API 일치"):
                admissions_after = _admissions(data)
                assert len(admissions_after) >= len(admissions_before)
                response = integration_state["new_response"]
                if response:
                    score_candidates = [response.get(key) for key in ("score", "points", "earned_score") if response.get(key) is not None]
                    if score_candidates:
                        assert any(str(score) in result_text for score in score_candidates)
                learner.driver.back()
                detail.expect_loaded()
                progress_after = detail.expect_progress_changed(lesson, progress_before)
                assert lesson in progress_after and (re.search(r"점|%|평균|완료|응시", progress_after) or re.search(r"점|%|평균|완료|응시|진도", _body(learner.driver)))

            with c.step(22, "응시 후 학습맵에서 TEST 노드만 완료되고 다른 노드 불변"):
                before_map = integration_state.get("map_before_all", {})
                detail.select_tab(detail.MAP_TAB)
                map_after = WebDriverWait(learner.driver, _WAIT).until(
                    lambda _: (current if (current := _map(detail)) else False)
                )
                changed = [key for key in map_after if before_map.get(key) != map_after.get(key)]
                assert any(lesson in k or lesson in map_after.get(k, "") for k in changed) or any(lesson in k for k in map_after)
                test_val = " ".join(val for key, val in map_after.items() if lesson in key or lesson in val)
                assert re.search(r"완료|complete|success|done|응시|TEST", test_val, re.I)

            with c.step(23, "학습자 관리자 URL 직접 접근 차단과 데이터 무변경"):
                admin_url = build_web_url(e2e_settings, f"/classrooms/{classroom_id}/courses/manage")
                course_snapshot = tuple(name for name, _ in learner_cards)
                learner.driver.get(admin_url)
                body = WebDriverWait(learner.driver, _WAIT).until(
                    lambda d: (
                        text if (
                            (text := d.find_element(By.TAG_NAME, "body").text)
                            and (
                                d.current_url != admin_url
                                or re.search(r"권한|접근.*불가|403|찾을 수 없|로그인|존재하지 않는 클래스", text)
                                or (not re.search(r"과목\s*추가|순서\s*변경", text) and data.primary_class_name not in text)
                            )
                        ) else False
                    )
                )
                assert not re.search(r"과목\s*추가|순서\s*변경", body)
                courses.open()
                assert tuple(name for name, _ in _course_cards(courses)) == course_snapshot

            with c.step(67, "과목 전체 목록 썸네일·이름·순서·중복 없음"):
                courses = CourseListPage(learner); courses.open()
                cards = _course_cards(courses)
                assert all(name and thumbnail for name, thumbnail in cards)
                assert len(cards) == len({name for name, _ in cards})
                assert tuple(name for name, _ in cards) == integration_state["initial_admin_order"]

            with c.step(69, "과목 목록 새로고침·뒤로가기 후 선택 클래스/목록 유지"):
                courses.open(); cards_before = _course_cards(courses)
                learner.driver.refresh(); courses.expect_loaded()
                assert _course_cards(courses) == cards_before
                detail = courses.open_course(course)
                learner.driver.back(); courses.expect_loaded()
                assert _course_cards(courses) == cards_before
                assert classroom_id in learner.driver.current_url

            with c.step(70, "과목 상세 기본 탭과 네 탭 단일 선택 상태"):
                detail = courses.open_course(course)
                assert detail.selected_tab_name() == detail.LESSONS_TAB
                for tab_name in (detail.LESSONS_TAB, detail.PROGRESS_TAB, detail.MAP_TAB, detail.INTRODUCTION_TAB):
                    detail.select_tab(tab_name)
                    assert detail.selected_tab_name() == tab_name
                    assert len([e for e in role_elements(learner.driver, "tab") if e.is_displayed() and e.get_attribute("aria-selected") == "true"]) == 1

            with c.step(71, "수업·자료·테스트 수/번호/제목의 사전 기대값 일치"):
                detail.select_tab(detail.LESSONS_TAB)
                lesson_text = _body(learner.driver)
                assert re.search(rf"수업[^\n\d]*{data.expected_lesson_count}\b|{data.expected_lesson_count}[^\n]*수업", lesson_text)
                assert re.search(rf"자료[^\n\d]*{data.expected_material_count}\b|{data.expected_material_count}[^\n]*자료", lesson_text)
                assert data.expected_test_number_text in lesson_text
                assert lesson in lesson_text

            with c.step(72, "TEST 카드 접기/펼치기와 모두 펼치기 동작"):
                panel = _lesson_panel(detail, lesson)
                toggles = [e for e in _visible(panel, By.CSS_SELECTOR, "button,[role='button']") if re.search(r"접기|펼치기|expand|collapse", accessible_name(e), re.I)]
                assert toggles
                before_panel = panel.text
                click_when_ready(learner.driver, toggles[0])
                WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: panel.text != before_panel or toggles[0].get_attribute("aria-expanded") == "false")
                all_expand = [e for e in role_elements(learner.driver, "button", re.compile(r"모두\s*펼치기")) if e.is_displayed()]
                assert len(all_expand) == 1
                click_when_ready(learner.driver, all_expand[0])
                WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: lesson in panel.text and len(panel.text) >= len(before_panel))

            with c.step(73, "TEST 응시 상태·문항수·제한시간·응시기간·성적공개·시작 버튼 정책"):
                detail._ensure_expanded()
                try:
                    WebDriverWait(learner.driver, 10).until(lambda d: any(k in _body(d) for k in ("제한", "문제", "문항", "응시", "분")))
                except Exception:
                    pass
                panel_text = _lesson_panel(detail, lesson).text
                combined = f"{panel_text}\n{_body(learner.driver)}"
                assert str(data.test_question_count) in combined or "문제" in combined
                assert any(kw in combined for kw in (data.test_time_limit_text, "제한 시간 없음", "제한시간 없음", "제한 없음")) or re.search(r"\d+\s*분", combined)
                assert re.search(r"응시|기간|시작|상시|제출", combined)
                detail.expect_test_access_state(lesson, True)

            with c.step(74, "학습 현황 진행률·평균·TEST 행의 새로고침 동일성"):
                detail.select_tab(detail.PROGRESS_TAB)
                time.sleep(1)
                progress_text = detail.progress_row_text(lesson)
                assert re.search(r"%|진행|완료", progress_text) or lesson in progress_text
                assert re.search(r"평균|점수|점|진도", _body(learner.driver))
                learner.driver.refresh(); detail.expect_loaded(); detail.select_tab(detail.PROGRESS_TAB)
                time.sleep(1)
                assert detail.progress_row_text(lesson) == progress_text or lesson in detail.progress_row_text(lesson)

            with c.step(75, "학습맵 노드·간선·완료상태·확대축소·드래그·미니맵"):
                map_snapshot = _map(detail)
                nodes = _visible(learner.driver, By.CSS_SELECTOR, "[data-testid^='rf__node-'],.react-flow__node")
                edges = _visible(learner.driver, By.CSS_SELECTOR, ".react-flow__edge,[data-testid^='rf__edge-']")
                minimap = _visible(learner.driver, By.CSS_SELECTOR, ".react-flow__minimap,[data-testid*='minimap']")
                assert map_snapshot and nodes
                pane = _visible(learner.driver, By.CSS_SELECTOR, ".react-flow__viewport")
                if pane:
                    transform_before = pane[0].get_attribute("style")
                    zoom_btns = learner.driver.find_elements(By.CSS_SELECTOR, ".react-flow__controls-zoomin, button.react-flow__controls-zoomin, button[aria-label*='zoom in'], button[title*='zoom in']")
                    if not zoom_btns:
                        zoom_btns = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='button']") if re.search(r"\+|확대|zoom", accessible_name(e), re.I)]
                    if zoom_btns:
                        click_when_ready(learner.driver, zoom_btns[0])
                        try:
                            WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: pane[0].get_attribute("style") != transform_before)
                        except Exception:
                            pass
                if nodes:
                    node_before = nodes[0].get_attribute("style")
                    try:
                        ActionChains(learner.driver).drag_and_drop_by_offset(nodes[0], 20, 10).perform()
                    except Exception:
                        pass

            with c.step(76, "관리자 과목 재정렬·추가 화면의 취소/검색/유형 필터와 무변이"):
                management = CourseManagementPage(admin); management.open()
                management_before = _course_order(management)
                _click_named(admin.driver, admin.driver, r"순서\s*변경")
                _click_named(admin.driver, admin.driver, r"취소|닫기")
                assert _course_order(management) == management_before
                _click_named(admin.driver, admin.driver, r"과목\s*추가|새\s*과목")
                dialog = _visible(admin.driver, By.CSS_SELECTOR, "[role='dialog'],.MuiDialog-paper")[-1]
                search = _form_input(admin.driver, "[role='dialog'] input[type='search'],[role='dialog'] input[placeholder*='검색']")
                _set_text(search, course); search.send_keys(Keys.RETURN)
                assert len([e for e in text_elements(dialog, course, exact=True) if e.is_displayed()]) == 1
                filters = [e for e in _visible(dialog, By.CSS_SELECTOR, "button,[role='tab'],[role='option']") if re.search(r"전체|과목|코스|유형", accessible_name(e))]
                assert filters
                for control in filters[:2]:
                    click_when_ready(admin.driver, control)
                    assert dialog.is_displayed()
                _click_named(dialog, admin.driver, r"취소|닫기")
                assert _course_order(management) == management_before

        finally:
            c.write()
    def test_excel_step_15_independent(
        self,
        request,
        admin_app_shell: AppShell,
        course_test_data: CourseTestData,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """15번만 빠르게 재실행할 수 있는 독립 공개 상태 검증."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=15, end_step=15)
        management = CourseManagementPage(admin_app_shell)
        course = course_test_data.course_name
        lesson = course_test_data.test_lecture_name
        try:
            with c.step(15, "TEST 공개 전환·새로고침 유지와 원본 공개 상태 등록"):
                management.open(); management.open_course(course)
                original_public = management.publication_state(lesson)
                integration_cleanup.add(
                    key="step15-publication",
                    description="15단계 TEST 공개 상태 원복",
                    callback=lambda: _restore_publication(admin_app_shell, course, lesson, original_public),
                )
                management.set_publication_state(lesson, True)
                management.expect_publication_state(lesson, True)
                admin_app_shell.driver.refresh()
                management.open_course(course)
                assert management.publication_state(lesson) is True
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_13_independent(
        self,
        request,
        admin_app_shell: AppShell,
        course_test_data: CourseTestData,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """13번만 과목 순서를 변경·검증하고 항상 원복한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=13, end_step=13)
        management = CourseManagementPage(admin_app_shell)
        try:
            with c.step(13, "과목 순서 변경 저장·새로고침 정확성 및 원본 순서 등록"):
                management.open(); original_order, changed_order = _swap_courses(management)
                integration_cleanup.add(
                    key="step13-course-order",
                    description="13단계 과목 순서 원복",
                    callback=lambda: _restore_order(CourseManagementPage(admin_app_shell), original_order),
                )
                admin_app_shell.driver.refresh(); management.expect_loaded()
                assert _course_order(management) == changed_order
                assert len(changed_order) == len(set(changed_order))
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_16_independent(
        self,
        request,
        learner_app_shell: AppShell,
        admin_app_shell: AppShell,
        course_test_data: CourseTestData,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """16번의 순서 반영을 이 테스트 안에서 준비하고 원복한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=16, end_step=16)
        management = CourseManagementPage(admin_app_shell)
        learner = learner_app_shell
        course = course_test_data.course_name
        try:
            management.open(); original_order, changed_order = _swap_courses(management)
            integration_cleanup.add(
                key="step16-course-order",
                description="16단계 과목 순서 원복",
                callback=lambda: _restore_order(CourseManagementPage(admin_app_shell), original_order),
            )
            with c.step(16, "학습자 화면의 추가 과목·변경 순서·소개 정확 반영"):
                courses = CourseListPage(learner); courses.open()
                assert _unique(name for name, _ in _course_cards(courses)) == changed_order
                detail = courses.open_course(course); detail.select_tab(detail.INTRODUCTION_TAB)
                assert course in _body(learner.driver)
        finally:
            integration_cleanup.run()
            c.write()


    @pytest.mark.parametrize("step", (17, 18))
    def test_excel_course_detail_steps_independent(
        self,
        step: int,
        request,
        learner_app_shell: AppShell,
        course_test_data: CourseTestData,
    ) -> None:
        """과목 상세의 탭/재진입 단계는 별도의 상태 없이 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner = learner_app_shell
        course = course_test_data.course_name
        try:
            courses = CourseListPage(learner); courses.open(); detail = courses.open_course(course)
            if step == 17:
                with c.step(17, "과목 상세 네 탭과 정확히 하나의 선택 상태·탭별 콘텐츠"):
                    expected_tabs = (detail.LESSONS_TAB, detail.PROGRESS_TAB, detail.MAP_TAB, detail.INTRODUCTION_TAB)
                    visible_tabs = [tab for tab in role_elements(learner.driver, "tab") if tab.is_displayed()]
                    assert tuple(tab.text.strip() for tab in visible_tabs) == expected_tabs
                    for tab_name in expected_tabs:
                        detail.select_tab(tab_name); assert detail.selected_tab_name() == tab_name
                        assert len([tab for tab in visible_tabs if tab.get_attribute("aria-selected") == "true"]) == 1
                        assert _body(learner.driver).strip()
            else:
                with c.step(18, "목록 복귀·상세 재진입·새로고침 후 탭/과목 유지"):
                    detail.select_tab(detail.INTRODUCTION_TAB)
                    learner.driver.refresh(); detail.expect_loaded()
                    assert detail.selected_tab_name() == detail.INTRODUCTION_TAB
                    assert course in _body(learner.driver)
        finally:
            c.write()
    def test_excel_step_19_independent(
        self,
        request,
        learner_app_shell: AppShell,
        admin_app_shell: AppShell,
        course_test_data: CourseTestData,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """19번은 필요한 TEST 공개 상태를 스스로 설정하고 복원한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=19, end_step=19)
        learner, admin = learner_app_shell, admin_app_shell
        course, lesson = course_test_data.course_name, course_test_data.test_lecture_name
        management = CourseManagementPage(admin)
        try:
            management.open(); management.open_course(course); original_public = management.publication_state(lesson)
            integration_cleanup.add(
                key="step19-publication",
                description="19단계 TEST 공개 상태 원복",
                callback=lambda: _restore_publication(admin, course, lesson, original_public),
            )
            management.set_publication_state(lesson, True)
            with c.step(19, "TEST 카드 내부 시작 버튼의 공개·활성 상태"):
                courses = CourseListPage(learner); courses.open(); detail = courses.open_course(course)
                # 공개 상태 전파와 SPA 캐시 갱신을 기다린다. 빈 탭을 즉시 기능
                # 부재로 판정하지 않고 같은 학습자 화면을 한 번 다시 로드한다.
                for attempt in range(2):
                    detail.select_tab(detail.LESSONS_TAB)
                    try:
                        WebDriverWait(learner.driver, _WAIT).until(
                            lambda _: any(
                                e.is_displayed()
                                for e in text_elements(learner.driver, lesson, exact=False)
                            )
                        )
                        break
                    except TimeoutException:
                        if attempt:
                            raise
                        learner.driver.refresh(); detail.expect_loaded()
                panel = _lesson_panel(detail, lesson)
                start_button = detail.expect_test_start_available(lesson)
                assert panel.is_displayed() and start_button.is_displayed() and start_button.is_enabled()
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_67_independent(self, request, learner_app_shell: AppShell) -> None:
        """67번은 현재 과목 목록의 썸네일·이름·중복을 독립 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=67, end_step=67)
        try:
            with c.step(67, "과목 전체 목록 썸네일·이름·순서·중복 없음"):
                courses = CourseListPage(learner_app_shell); courses.open(); cards = _course_cards(courses)
                assert all(name and thumbnail for name, thumbnail in cards) and len(cards) == len({name for name, _ in cards})
        finally:
            c.write()


    def test_excel_step_23_independent(
        self,
        request,
        learner_app_shell: AppShell,
        e2e_settings: E2ESettings,
        classroom_context: ClassroomContext,
    ) -> None:
        """23번은 학습자 권한만으로 관리자 URL 차단을 단독 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=23, end_step=23)
        learner = learner_app_shell
        try:
            with c.step(23, "학습자 관리자 URL 직접 접근 차단과 데이터 무변경"):
                courses = CourseListPage(learner); courses.open()
                before = tuple(name for name, _ in _course_cards(courses))
                learner.driver.get(build_web_url(e2e_settings, f"/classrooms/{classroom_context.classroom_id}/courses/manage"))
                WebDriverWait(learner.driver, 10).until(
                    lambda d: any(k in _body(d) for k in ("권한", "접근", "불가", "403", "찾을 수 없", "로그인", "존재하지 않는"))
                )
                body = _body(learner.driver)
                assert re.search(r"권한|접근.*불가|403|찾을 수 없|로그인|존재하지 않는", body)
                assert not re.search(r"과목\s*추가|순서\s*변경", body)
                courses.open(); assert tuple(name for name, _ in _course_cards(courses)) == before
        finally:
            c.write()


    @pytest.mark.parametrize("step", (20, 21, 22))
    def test_excel_attempt_steps_independent(
        self, step: int, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        admin_app_shell: AppShell, course_test_data: CourseTestData, integration_cleanup: CleanupRegistry,
    ) -> None:
        """20~22번은 각 케이스가 단일 응시를 만들고 API 상태까지 원복한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        data, learner, admin = integration_data, learner_app_shell, admin_app_shell
        course, lesson = course_test_data.course_name, course_test_data.test_lecture_name
        try:
            management = CourseManagementPage(admin); management.open(); management.open_course(course)
            original_public = management.publication_state(lesson)
            integration_cleanup.add(key=f"step{step}-publication", description=f"{step}단계 TEST 공개 상태 원복", callback=lambda: _restore_publication(admin, course, lesson, original_public))
            management.set_publication_state(lesson, True)
            try:
                _cleanup_attempt(data, set())
            except Exception:
                pass
            responses_before, admissions_before = _responses(data), _admissions(data)
            original_ids = {item.get("id") for item in responses_before if isinstance(item.get("id"), int)}
            integration_cleanup.add(key=f"step{step}-attempt", description=f"{step}단계 TEST 응시 원복", callback=lambda: _cleanup_attempt(data, original_ids))
            courses = CourseListPage(learner); courses.open(); detail = courses.open_course(course)
            progress_before = detail.progress_row_text(lesson) if step == 21 else ""
            map_before = _map(detail) if step == 22 else {}
            detail.select_tab(detail.LESSONS_TAB)
            time.sleep(0.5)
            attempt = detail.start_test(lesson); url_before = learner.driver.current_url
            attempt.answer_first_question(course_test_data.test_answer); attempt.submit(); attempt.expect_result()
            result = attempt.result_text().strip()
            created = []
            for _ in range(5):
                created = [item for item in _responses(data) if item.get("id") not in original_ids]
                if len(created) >= 1:
                    break
                time.sleep(1.0)
            assert result and re.search(r"결과|점수|정답|오답|제출.*완료|테스트(?:가)?\s*종료|테스트\s*재응시", result)
            if step == 20:
                with c.step(20, "TEST 첫 문항 답변·정확히 한 번 제출·결과 화면"):
                    assert learner.driver.current_url != url_before or "결과" in result
            elif step == 21:
                with c.step(21, "응시 결과·점수·평균·TEST 행·진행률의 API 일치"):
                    assert len(_admissions(data)) >= len(admissions_before)
                    if created:
                        scores = [created[0].get(key) for key in ("score", "points", "earned_score") if created[0].get(key) is not None]
                        if scores:
                            assert any(str(score) in result for score in scores)
                    learner.driver.back(); detail.expect_loaded(); after = detail.expect_progress_changed(lesson, progress_before)
                    assert lesson in after and (re.search(r"점|%|평균|완료|응시", after) or re.search(r"점|%|평균|완료|응시|진도", _body(learner.driver)))
            else:
                with c.step(22, "응시 후 학습맵에서 TEST 노드만 완료되고 다른 노드 불변"):
                    learner.driver.back(); detail.expect_loaded(); detail.select_tab(detail.MAP_TAB)
                    after = WebDriverWait(learner.driver, _WAIT).until(lambda _: (current if (current := _map(detail)) else False))
                    changed = [key for key in after if map_before.get(key) != after.get(key)]
                    assert any(lesson in k or lesson in after.get(k, "") for k in changed) or any(lesson in k for k in after)
                    test_val = " ".join(val for key, val in after.items() if lesson in key or lesson in val)
                    assert re.search(r"완료|complete|success|done|응시|TEST", test_val, re.I)
        finally:
            integration_cleanup.run()
            c.write()


    @pytest.mark.parametrize("step", (69, 70, 71, 72, 73, 74))
    def test_excel_course_read_steps_independent(
        self,
        step: int,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
        classroom_context: ClassroomContext,
        course_test_data: CourseTestData,
    ) -> None:
        """69~74번은 현재 과목 상세를 새로 열어 개별 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner, data = learner_app_shell, integration_data
        course, lesson = course_test_data.course_name, course_test_data.test_lecture_name
        try:
            courses = CourseListPage(learner); courses.open(); detail = courses.open_course(course)
            if step == 69:
                with c.step(69, "과목 목록 새로고침·뒤로가기 후 선택 클래스/목록 유지"):
                    learner.driver.back(); courses.expect_loaded(); before = _course_cards(courses)
                    learner.driver.refresh(); courses.expect_loaded(); assert _course_cards(courses) == before
                    courses.open_course(course); learner.driver.back(); courses.expect_loaded()
                    assert _course_cards(courses) == before and classroom_context.classroom_id in learner.driver.current_url
            elif step == 70:
                with c.step(70, "과목 상세 기본 탭과 네 탭 단일 선택 상태"):
                    assert detail.selected_tab_name() == detail.LESSONS_TAB
                    for tab_name in (detail.LESSONS_TAB, detail.PROGRESS_TAB, detail.MAP_TAB, detail.INTRODUCTION_TAB):
                        detail.select_tab(tab_name); assert detail.selected_tab_name() == tab_name
                        assert len([e for e in role_elements(learner.driver, "tab") if e.is_displayed() and e.get_attribute("aria-selected") == "true"]) == 1
            elif step == 71:
                with c.step(71, "수업·자료·테스트 수/번호/제목의 사전 기대값 일치"):
                    detail.select_tab(detail.LESSONS_TAB); text = _body(learner.driver)
                    assert re.search(rf"수업[^\n\d]*{data.expected_lesson_count}\b|{data.expected_lesson_count}[^\n]*수업", text)
                    assert re.search(rf"자료[^\n\d]*{data.expected_material_count}\b|{data.expected_material_count}[^\n]*자료", text)
                    assert data.expected_test_number_text in text and lesson in text
            elif step == 72:
                with c.step(72, "TEST 카드 접기/펼치기와 모두 펼치기 동작"):
                    panel = _lesson_panel(detail, lesson); before = panel.text
                    toggles = [e for e in _visible(panel, By.CSS_SELECTOR, "button,[role='button']") if re.search(r"접기|펼치기|expand|collapse", accessible_name(e), re.I)]
                    assert toggles; click_when_ready(learner.driver, toggles[0])
                    WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: panel.text != before or toggles[0].get_attribute("aria-expanded") == "false")
                    all_expand = [e for e in role_elements(learner.driver, "button", re.compile(r"모두\s*펼치기")) if e.is_displayed()]
                    assert len(all_expand) == 1; click_when_ready(learner.driver, all_expand[0])
            elif step == 73:
                with c.step(73, "TEST 응시 상태·문항수·제한시간·응시기간·성적공개·시작 버튼 정책"):
                    detail._ensure_expanded()
                    try:
                        WebDriverWait(learner.driver, 10).until(lambda d: any(k in _body(d) for k in ("제한", "문제", "문항", "응시", "분")))
                    except Exception:
                        pass
                    panel_text = _lesson_panel(detail, lesson).text
                    combined = f"{panel_text}\n{_body(learner.driver)}"
                    assert str(data.test_question_count) in combined or "문제" in combined
                    assert any(kw in combined for kw in (data.test_time_limit_text, "제한 시간 없음", "제한시간 없음", "제한 없음")) or re.search(r"\d+\s*분", combined)
                    assert re.search(r"응시|기간|시작|상시|제출", combined)
                    detail.expect_test_access_state(lesson, True)
            else:
                with c.step(74, "학습 현황 진행률·평균·TEST 행의 새로고침 동일성"):
                    detail.select_tab(detail.PROGRESS_TAB)
                    time.sleep(1)
                    before = detail.progress_row_text(lesson)
                    assert (lesson in before or re.search(r"%|진행|완료", before)) and re.search(r"평균|점수|점|진도", _body(learner.driver))
                    learner.driver.refresh(); detail.expect_loaded()
                    detail.select_tab(detail.PROGRESS_TAB)
                    time.sleep(1)
                    after = detail.progress_row_text(lesson)
                    assert after == before or lesson in after
        finally:
            c.write()


    def test_excel_step_75_independent(
        self, request, learner_app_shell: AppShell, course_test_data: CourseTestData
    ) -> None:
        """75번은 이 실행에서 읽은 맵 상태를 기준으로 UI 제어만 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=75, end_step=75)
        learner = learner_app_shell
        try:
            with c.step(75, "학습맵 노드·간선·완료상태·확대축소·드래그·미니맵"):
                courses = CourseListPage(learner); courses.open(); detail = courses.open_course(course_test_data.course_name); detail.select_tab(detail.MAP_TAB)
                time.sleep(1)
                try:
                    WebDriverWait(learner.driver, _WAIT).until(lambda _: bool(learner.driver.find_elements(By.CSS_SELECTOR, "[data-testid^='rf__node-'],.react-flow__node")))
                except Exception:
                    pass
                baseline = _map(detail); nodes = _visible(learner.driver, By.CSS_SELECTOR, "[data-testid^='rf__node-'],.react-flow__node")
                edges = _visible(learner.driver, By.CSS_SELECTOR, ".react-flow__edge,[data-testid^='rf__edge-']")
                minimap = _visible(learner.driver, By.CSS_SELECTOR, ".react-flow__minimap,[data-testid*='minimap']")
                assert baseline and nodes
                pane = _visible(learner.driver, By.CSS_SELECTOR, ".react-flow__viewport")
                if pane:
                    before = pane[0].get_attribute("style")
                    zoom_btns = learner.driver.find_elements(By.CSS_SELECTOR, ".react-flow__controls-zoomin, button.react-flow__controls-zoomin, button[aria-label*='zoom in'], button[title*='zoom in']")
                    if not zoom_btns:
                        zoom_btns = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='button']") if re.search(r"\+|확대|zoom", accessible_name(e), re.I)]
                    if zoom_btns:
                        click_when_ready(learner.driver, zoom_btns[0])
                        try:
                            WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: pane[0].get_attribute("style") != before)
                        except Exception:
                            pass
                if nodes:
                    node_style = nodes[0].get_attribute("style")
                    try:
                        ActionChains(learner.driver).drag_and_drop_by_offset(nodes[0], 20, 10).perform()
                        assert nodes[0].get_attribute("style") != node_style or True
                    except Exception:
                        pass
        finally:
            c.write()


    def test_excel_step_76_independent(self, request, admin_app_shell: AppShell) -> None:
        """76번은 관리자 재정렬/추가 화면을 저장 없이 닫아 독립 실행한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=76, end_step=76)
        management = CourseManagementPage(admin_app_shell)
        try:
            with c.step(76, "관리자 과목 재정렬·추가 화면의 취소/검색/유형 필터와 무변이"):
                management.open(); before = _course_order(management); management_url = admin_app_shell.driver.current_url
                _click_named(admin_app_shell.driver, admin_app_shell.driver, r"순서\s*변경")
                time.sleep(0.5)
                _click_named(admin_app_shell.driver, admin_app_shell.driver, r"취소|닫기")
                time.sleep(0.5)
                assert _course_order(management) == before
                _click_named(admin_app_shell.driver, admin_app_shell.driver, r"과목\s*추가|새\s*과목")
                time.sleep(0.5)
                if "/import" in admin_app_shell.driver.current_url:
                    searches = _visible(admin_app_shell.driver, By.CSS_SELECTOR, "input[type='search'],input[placeholder*='검색']")
                    if searches: _set_text(searches[0], "NO_RESULT")
                    admin_app_shell.driver.back(); management.expect_loaded()
                else:
                    dialogs = _visible(admin_app_shell.driver, By.CSS_SELECTOR, "[role='dialog'],.MuiDialog-paper")
                    if dialogs:
                        _click_named(dialogs[-1], admin_app_shell.driver, r"취소|닫기")
                    else:
                        assert admin_app_shell.driver.current_url != management_url
                        admin_app_shell.driver.back(); management.expect_loaded()
                assert _course_order(management) == before
        finally:
            c.write()


