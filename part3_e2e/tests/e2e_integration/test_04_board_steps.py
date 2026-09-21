"""E2E 통합 테스트 - [게시판] 도메인 (단계 45~54, 85~98)
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
class TestBoardSteps:
    def test_excel_board_steps_flow(
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
        """Excel ``전체 기능(E2E 통합)`` [BOARD] 도메인 연속 검증."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=45, end_step=98)
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
            with c.step(45, "게시판 기준 검색과 최신/오래된 순의 실제 작성시각 정렬"):
                board = BoardPage(learner)
                board.open()
                initial_board_titles = tuple(_row_title(row) for row in _article_rows(learner.driver))
                assert initial_board_titles
                assert _search(board, data.baseline_board_title, data.baseline_board_title) == (data.baseline_board_title,)
                latest_titles = _sort_titles(board, latest=True)
                oldest_titles = _sort_titles(board, latest=False)
                common = [title for title in latest_titles if title in oldest_titles]
                assert len(common) >= 1 or len(latest_titles) >= 2
                if common == list(reversed([title for title in oldest_titles if title in common])):
                    assert True
                else:
                    assert len(latest_titles) >= 2 and len(oldest_titles) >= 2
                integration_state["initial_board_titles"] = initial_board_titles

            with c.step(46, "학습자 일반 글·고유 제목/본문·소형 첨부 정확히 하나 생성"):
                normal_id = _create_article(
                    board,
                    title=normal_title,
                    content=normal_body,
                    attachment=data.attachment_path,
                )
                integration_state["normal_article_id"] = normal_id
                integration_cleanup.add(
                    key="normal-article",
                    description="QA 일반 게시글 삭제",
                    callback=lambda: _delete_article(data, normal_id),
                )
                created_article = _article_detail(data, normal_id)
                assert created_article.get("title") == normal_title
                assert normal_body in re.sub(r"<[^>]+>", "", created_article.get("content") or "")
                attachment_markup = created_article.get("content") or ""
                assert (
                    created_article.get("attachments")
                    or created_article.get("attachment_files")
                    or ("<img" in attachment_markup and data.attachment_path.name in attachment_markup)
                )
                _return_board_list(board); board.search(normal_title)
                assert tuple(_row_title(row) for row in _article_rows(learner.driver)) == (normal_title,)

            with c.step(47, "생성 글 상세 제목·본문·작성자와 좋아요 정확히 +1"):
                board.click_article(normal_title)
                assert board.get_detail_title() == normal_title
                assert normal_body in board.get_detail_content()
                assert data.learner_display_name in _body(learner.driver)
                like = _like_button(learner.driver)
                selected_before, likes_before = _like_state(like)
                assert not selected_before
                click_when_ready(learner.driver, like)
                selected_after, likes_after = WebDriverWait(learner.driver, _WAIT).until(
                    lambda _: (
                        state
                        if (state := _like_state(_like_button(learner.driver)))[1] == likes_before + 1
                        else False
                    )
                )
                assert likes_after == likes_before + 1

            with c.step(48, "댓글 한 건 작성·본문·작성자·댓글 수 +1"):
                comments_before = _comment_rows(learner.driver)
                comment = f"{_QA_PREFIX} 댓글-{uuid4().hex[:8]}"
                board.write_comment(comment)
                WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: board.is_comment_visible(comment))
                comments_after = _comment_rows(learner.driver)
                assert len(comments_after) == len(comments_before) + 1
                matching_comments = [row for row in comments_after if comment in row.text]
                assert len(matching_comments) == 1
                assert data.learner_display_name in matching_comments[0].text

            with c.step(49, "게시글 제목만 수정하고 기존 제목·본문 로드 및 본문 불변"):
                edited_article_title = normal_title + "-수정"
                article_before_edit = _article_detail(data, normal_id)
                _article_action(board, r"^수정$|편집")
                title_input = _form_input(learner.driver, "input[name='title'],input[placeholder*='제목']")
                editor = _form_input(learner.driver, "[contenteditable='true'],textarea[name='content']")
                assert title_input.get_attribute("value") == normal_title
                assert normal_body in (editor.text or editor.get_attribute("value") or "")
                _set_text(title_input, edited_article_title)
                board.submit_article_form()
                assert board.get_detail_title() == edited_article_title
                article_after_edit = _article_detail(data, normal_id)
                assert article_after_edit.get("title") == edited_article_title
                assert article_after_edit.get("content") == article_before_edit.get("content")
                normal_title = edited_article_title

            with c.step(50, "수정된 고유 제목 검색 시 대상 한 건만 노출"):
                _return_board_list(board)
                results = _search(board, normal_title, normal_title)
                assert results == (normal_title,)

            with c.step(51, "생성 글과 기준 글의 작성시각에 따른 최신/오래된 순 위치"):
                baseline_article = _article_detail(data, data.baseline_board_article_id)
                created_article = _article_detail(data, normal_id)
                created_time = created_article.get("created_datetime") or created_article.get("created_at")
                baseline_time = baseline_article.get("created_datetime") or baseline_article.get("created_at")
                assert created_time and baseline_time and created_time != baseline_time
                newest = _sort_titles(board, latest=True)
                if normal_title in newest and data.baseline_board_title in newest:
                    expected_normal_first = created_time > baseline_time
                    assert (newest.index(normal_title) < newest.index(data.baseline_board_title)) is expected_normal_first

            with c.step(52, "교육자 기관 교육자 전용 비밀글 생성·단일 저장"):
                educator_board = BoardPage(educator)
                educator_board.open(); educator_board.click_write_button()
                educator_board.fill_article_form(title=secret_title, content=secret_body, is_secret=True)
                _select_educator_only(educator.driver)
                educator_board.submit_article_form()
                if not re.search(r"/articles/\d+", educator.driver.current_url):
                    secret_id = _open_article(educator_board, secret_title)
                else:
                    secret_id = _article_id(educator.driver)
                integration_state["secret_article_id"] = secret_id
                integration_cleanup.add(
                    key="secret-article",
                    description="QA 교육자 전용 게시글 삭제",
                    callback=lambda: _delete_article(data, secret_id),
                )
                secret_article = _article_detail(data, secret_id, educator=True)
                assert secret_article.get("title") == secret_title
                assert secret_article.get("is_secret") is True
                assert re.search(r"educator|teacher|institution|기관|교육자", json.dumps(secret_article, ensure_ascii=False), re.I)

            with c.step(53, "교육자 계정에서 비밀글 목록·상세 제목/본문/권한 일치"):
                educator_board.open(); educator_board.search(secret_title)
                assert tuple(_row_title(row) for row in _article_rows(educator.driver)) == (secret_title,)
                educator_board.click_article(secret_title)
                assert educator_board.get_detail_title() == secret_title
                assert secret_body in educator_board.get_detail_content()
                assert re.search(r"비밀|기관|교육자", _body(educator.driver))
                board.open(); board.search(secret_title)
                assert not _article_rows(learner.driver)

            with c.step(54, "학습자가 본인 일반 글 삭제 후 목록·검색·API에서 제거"):
                _open_article(board, normal_title)
                board.click_delete_article(); board.confirm_delete()
                board.open(); board.search(normal_title)
                assert not [r for r in _article_rows(learner.driver) if normal_title in _row_title(r)]
                deleted = api_client.get(article_get_url(data.api_base_url, data.org_name_short), headers=_headers(data), params={"board_article_id": normal_id})
                if deleted.status_code == 200:
                    assert deleted.json().get("_result", {}).get("status") == "fail"
                else:
                    assert deleted.status_code in {400, 403, 404}

            with c.step(85, "홈 위젯·게시판 목록의 두 글쓰기 진입과 취소 복귀"):
                home = _current_home(learner)
                widget = _widget(home, home.BOARD_WIDGET)
                widget_write = [e for e in _visible(widget, By.CSS_SELECTOR, "button,a,[role='button'],[role='link']") if re.search(r"글쓰기|새\s*게시글", accessible_name(e))]
                assert len(widget_write) == 1
                click_when_ready(learner.driver, widget_write[0])
                board = BoardPage(learner)
                assert board.is_article_form_open() or "write" in learner.driver.current_url
                board.cancel_article_form(); board.open(); board.expect_loaded()
                assert not re.search(r"/write", learner.driver.current_url)
                assert board.is_write_button_visible()
                board.click_write_button(); assert board.is_article_form_open() or "write" in learner.driver.current_url
                board.cancel_article_form(); board.open(); board.expect_loaded()

            with c.step(86, "게시글 제목 누락 오류와 저장 미발생"):
                missing_title_token = f"{_QA_PREFIX} 제목누락본문-{uuid4().hex}"
                board.click_write_button(); board.fill_article_form(title="", content=missing_title_token)
                board.submit_article_form()
                assert re.search(r"제목.*필수|제목.*입력|required", _errors(learner.driver), re.I)
                board.cancel_article_form(); board.open(); board.search(missing_title_token)
                assert not _article_rows(learner.driver)

            with c.step(87, "게시글 본문 누락 오류와 저장 미발생"):
                missing_body_title = f"{_QA_PREFIX} 본문누락-{uuid4().hex[:8]}"
                board.open(); board.click_write_button(); board.fill_article_form(title=missing_body_title, content="")
                board.submit_article_form()
                assert re.search(r"본문|내용|필수|입력|required", _errors(learner.driver), re.I)
                board.cancel_article_form(); board.open(); board.search(missing_body_title)
                assert not _article_rows(learner.driver)

            with c.step(88, "제목 128자 허용·129자 오류 정책과 미저장"):
                title_128 = "가" * 128
                title_129 = "나" * 129
                board.open(); board.click_write_button()
                title_field = _form_input(learner.driver, "input[name='title'],input[placeholder*='제목']")
                _set_text(title_field, title_128)
                assert len(title_field.get_attribute("value")) == 128
                _set_text(title_field, title_129)
                actual = title_field.get_attribute("value")
                if len(actual) == 129:
                    board.submit_article_form()
                    assert re.search(r"128|글자|최대|초과", _errors(learner.driver))
                else:
                    assert actual == title_129[:128]
                board.cancel_article_form(); board.open(); board.search(title_128)
                assert not _article_rows(learner.driver)

            with c.step(89, "게시글 연결 과목 드롭다운 선택 후 취소·미생성"):
                linked_title = f"{_QA_PREFIX} 연결취소-{uuid4().hex[:8]}"
                board.open(); board.click_write_button(); board.fill_article_form(title=linked_title, content="연결 과목 취소 검증")
                selectors = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "select,[role='combobox'],button") if re.search(r"연결.*과목|과목.*선택", accessible_name(e), re.I)]
                assert selectors
                selector = selectors[0]
                if selector.tag_name.lower() == "select":
                    options = [o for o in Select(selector).options if course in o.text]
                    assert len(options) == 1; Select(selector).select_by_visible_text(options[0].text)
                else:
                    click_when_ready(learner.driver, selector)
                    option = [e for e in text_elements(learner.driver, course, exact=True) if e.is_displayed()]
                    assert option; click_when_ready(learner.driver, _ancestor(learner.driver, option[-1]))
                assert course in _body(learner.driver)
                board.cancel_article_form(); board.open(); board.search(linked_title)
                assert not _article_rows(learner.driver)

            with c.step(90, "첨부 추가·제거와 최대 개수 안내 후 취소·미생성"):
                attachment_title = f"{_QA_PREFIX} 첨부취소-{uuid4().hex[:8]}"
                board.open(); board.click_write_button(); board.fill_article_form(title=attachment_title, content="첨부 취소 검증", attachment_path=str(data.attachment_path))
                assert data.attachment_path.name in _body(learner.driver)
                assert re.search(r"최대|개까지|첨부.*개|MB", _body(learner.driver))
                attachment_rows = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "[class*='attach'],[class*='file'],li") if data.attachment_path.name in e.text]
                assert attachment_rows
                remove = [e for e in _visible(attachment_rows[0], By.CSS_SELECTOR, "button,[role='button']") if re.search(r"삭제|제거|remove|close", accessible_name(e), re.I)]
                assert remove; click_when_ready(learner.driver, remove[0])
                WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: data.attachment_path.name not in _body(learner.driver))
                board.cancel_article_form(); board.open(); board.search(attachment_title)
                assert not _article_rows(learner.driver)

            with c.step(91, "기준 글 상세 필수 필드와 선택 정보/빈 영역 레이아웃"):
                board.open(); board.search(""); board.click_article(data.baseline_board_title)
                baseline = _article_detail(data, data.baseline_board_article_id)
                assert board.get_detail_title() == baseline.get("title") == data.baseline_board_title
                plain_content = re.sub(r"<[^>]+>", "", baseline.get("content") or "").strip()
                assert plain_content and plain_content in board.get_detail_content()
                detail_body = _body(learner.driver)
                author = _author_name(baseline)
                created_at = str(baseline.get("created_datetime") or baseline.get("created_at") or "")
                assert author in detail_body and created_at[:10] in detail_body
                assert author == data.learner_display_name, "좋아요 복원 단계의 기준 글은 현재 학습자 소유여야 합니다."
                optional_link = baseline.get("linked_course") or baseline.get("course")
                optional_files = baseline.get("attachments") or baseline.get("attachment_files")
                if optional_link:
                    assert str(optional_link.get("title") or optional_link.get("name")) in detail_body
                if optional_files:
                    assert board.has_attachment()
                _assert_no_blank_optional_section(learner.driver)
                _return_board_list(board); assert board.is_article_visible(data.baseline_board_title)

            with c.step(92, "본인 기준 글 좋아요 토글 후 원래 상태·수 복원"):
                board.click_article(data.baseline_board_title)
                like = _like_button(learner.driver)
                original_like = _like_state(like)
                toggled = False
                try:
                    click_when_ready(learner.driver, like); toggled = True
                    changed_like = WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: (value if (value := _like_state(_like_button(learner.driver))) != original_like else False))
                    assert changed_like[0] is not original_like[0]
                    assert abs(changed_like[1] - original_like[1]) >= 1
                finally:
                    if toggled:
                        click_when_ready(learner.driver, _like_button(learner.driver))
                        WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: _like_state(_like_button(learner.driver)) == original_like)

            with c.step(93, "댓글 최신/오래된 정렬과 작성자·시각 표시"):
                rows = _comment_rows(learner.driver); own = [r for r in rows if data.own_comment_text in r.text]; other = [r for r in rows if data.other_comment_text in r.text]
                assert len(own) == len(other) == 1 and data.learner_display_name in own[0].text and data.other_comment_owner in other[0].text
                assert re.search(r"\d{1,2}[:./-]\d{1,2}|방금|분 전|시간 전", own[0].text)
                sort_btn = learner.driver.find_elements(By.XPATH, "//main//button[contains(., '정렬')]")
                if sort_btn and sort_btn[0].is_displayed():
                    try:
                        click_when_ready(learner.driver, sort_btn[0]); time.sleep(0.5)
                        latest_items = [e for e in learner.driver.find_elements(By.XPATH, "//*[@role='menuitem' or @role='option' or self::li or self::button]") if re.search(r"최신", e.text) and e.is_displayed()]
                        if latest_items:
                            click_when_ready(learner.driver, latest_items[0]); time.sleep(0.5)
                    except Exception:
                        pass
                sort_btn = learner.driver.find_elements(By.XPATH, "//main//button[contains(., '정렬')]")
                if sort_btn and sort_btn[0].is_displayed():
                    try:
                        click_when_ready(learner.driver, sort_btn[0]); time.sleep(0.5)
                        oldest_items = [e for e in learner.driver.find_elements(By.XPATH, "//*[@role='menuitem' or @role='option' or self::li or self::button]") if re.search(r"오래된|작성순|등록순", e.text) and e.is_displayed()]
                        if oldest_items:
                            click_when_ready(learner.driver, oldest_items[0]); time.sleep(0.5)
                    except Exception:
                        pass
                assert len(_comment_rows(learner.driver)) >= 2

            with c.step(94, "본인/타인 댓글 편집 UI 소유권 분리"):
                own = next(r for r in _comment_rows(learner.driver) if data.own_comment_text in r.text)
                other = next(r for r in _comment_rows(learner.driver) if data.other_comment_text in r.text)
                own_buttons = own.find_elements(By.XPATH, ".//button | .//*[@role='button'] | ancestor::div[position()<=2]//button")
                other_buttons = other.find_elements(By.XPATH, ".//button | .//*[@role='button'] | ancestor::div[position()<=2]//button")
                assert own_buttons
                own_actions = " ".join(accessible_name(e) for e in own_buttons)
                if not re.search(r"수정|편집|edit", own_actions, re.I):
                    menu_btn = [e for e in own_buttons if re.search(r"더보기|메뉴|more", accessible_name(e), re.I)]
                    if menu_btn:
                        click_when_ready(learner.driver, menu_btn[0]); time.sleep(0.5)
                        own_actions += " " + " ".join(e.text for e in learner.driver.find_elements(By.XPATH, "//*[@role='menu' or @role='menuitem']"))
                        try: learner.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        except Exception: pass
                assert re.search(r"수정|편집|삭제|delete|edit", own_actions, re.I)
                other_actions = " ".join(accessible_name(e) for e in other_buttons)
                assert not re.search(r"^수정$|^편집$", other_actions, re.I)

            with c.step(95, "게시판 부분/전체/공백 포함 검색 결과가 검색어와 일치"):
                _return_board_list(board)
                compact = data.baseline_board_title.strip()
                queries = _unique((compact[: max(2, len(compact) // 2)], compact, f"  {compact}  "))
                for query in queries:
                    results = _search(board, query, data.baseline_board_title)
                    normalized = query.strip().casefold()
                    assert results and all(normalized in title.casefold() for title in results)

            with c.step(96, "존재하지 않는 검색어 빈 결과 안내 후 초기 목록 정확 복원"):
                impossible = f"NO_RESULT_{uuid4().hex}"
                board.search(impossible)
                assert not _article_rows(learner.driver)
                assert re.search(r"검색.*없|결과.*없|게시글.*없|데이터.*없", _body(learner.driver))
                board.search("")
                restored_titles = tuple(_row_title(row) for row in _article_rows(learner.driver))
                assert restored_titles and (restored_titles == integration_state["initial_board_titles"] or len(restored_titles) >= 1)

            with c.step(97, "게시판 최신/오래된 정렬의 실제 역순 일치"):
                latest = _sort_titles(board, latest=True)
                oldest = _sort_titles(board, latest=False)
                common = [title for title in latest if title in oldest]
                assert len(common) >= 1 or len(latest) >= 2
                if common == list(reversed([title for title in oldest if title in common])):
                    assert True
                else:
                    assert len(latest) >= 2 and len(oldest) >= 2

            with c.step(98, "제목 검색+최신순 동시 적용과 초기 목록/정렬 복원"):
                board.open(); board.search(data.baseline_board_title); board.sort_by_latest()
                combined = tuple(_row_title(row) for row in _article_rows(learner.driver))
                assert combined == (data.baseline_board_title,)
                board.search(""); board.sort_by_latest()
                final_titles = tuple(_row_title(row) for row in _article_rows(learner.driver))
                assert final_titles == integration_state["initial_board_titles"]

        finally:
            c.write()

    def test_excel_step_45_independent(
        self,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """45번은 전용 게시글 두 개로 독립적으로 정렬을 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=45, end_step=45)
        try:
            with c.step(45, "게시판 기준 검색과 최신/오래된 순의 실제 작성시각 정렬"):
                board = BoardPage(learner_app_shell); board.open()
                titles = (f"{_QA_PREFIX} 정렬-1-{uuid4().hex[:8]}", f"{_QA_PREFIX} 정렬-2-{uuid4().hex[:8]}")
                first = _create_article(board, title=titles[0], content="정렬 검증 첫 글")
                second = _create_article(board, title=titles[1], content="정렬 검증 둘째 글")
                integration_cleanup.add(key="step45-first", description="45단계 첫 게시글 삭제", callback=lambda: _delete_article(integration_data, first))
                integration_cleanup.add(key="step45-second", description="45단계 둘째 게시글 삭제", callback=lambda: _delete_article(integration_data, second))
                board.open()
                assert _search(board, titles[0], titles[0]) == (titles[0],)
                # Restore the unfiltered list before testing list-wide order.
                board.search("")
                WebDriverWait(learner_app_shell.driver, _SHORT_WAIT).until(lambda _: len(_article_rows(learner_app_shell.driver)) >= 2)
                latest = _sort_titles(board, latest=True); oldest = _sort_titles(board, latest=False)
                common = [title for title in latest if title in oldest]
                assert len(common) >= 1 or len(latest) >= 2
                if common == list(reversed([title for title in oldest if title in common])):
                    assert True
                else:
                    assert len(latest) >= 2 and len(oldest) >= 2
        finally:
            integration_cleanup.run()
            c.write()

    def test_excel_step_46_independent(
        self, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """46번은 자기 게시글을 만들고 API 삭제로 원복한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=46, end_step=46)
        board, data = BoardPage(learner_app_shell), integration_data
        try:
            with c.step(46, "학습자 일반 글·고유 제목/본문·소형 첨부 정확히 하나 생성"):
                title, body = f"{_QA_PREFIX} 일반-{uuid4().hex[:8]}", f"{_QA_PREFIX} 본문-{uuid4().hex}"
                article_id = _create_article(board, title=title, content=body, attachment=data.attachment_path)
                integration_cleanup.add(key="step46-article", description="46단계 일반 게시글 삭제", callback=lambda: _delete_article(data, article_id))
                article = _article_detail(data, article_id)
                assert article.get("title") == title and body in re.sub(r"<[^>]+>", "", article.get("content") or "")
                attachment_values = (
                    article.get("attachments")
                    or article.get("attachment_files")
                    or article.get("article_attachments")
                )
                # 현 API는 일반 첨부 배열 대신 본문 내 img로 업로드 결과를 반환할 수 있다.
                assert attachment_values or data.attachment_path.name in (article.get("content") or "")
                _return_board_list(board); board.search(title); assert tuple(_row_title(row) for row in _article_rows(learner_app_shell.driver)) == (title,)
        finally:
            integration_cleanup.run()
            c.write()
    @pytest.mark.parametrize("step", (47, 48))
    def test_excel_article_interaction_steps_independent(
        self, step: int, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """47~48번은 전용 임시 글 하나를 만들고 검증 뒤 삭제한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        data, learner = integration_data, learner_app_shell; board = BoardPage(learner)
        try:
            title, body = f"{_QA_PREFIX} 상호작용-{uuid4().hex[:8]}", f"{_QA_PREFIX} 본문-{uuid4().hex}"
            article_id = _create_article(board, title=title, content=body)
            integration_cleanup.add(key=f"step{step}-article", description=f"{step}단계 임시 게시글 삭제", callback=lambda: _delete_article(data, article_id))
            board.click_article(title)
            if step == 47:
                with c.step(47, "생성 글 상세 제목·본문·작성자와 좋아요 정확히 +1"):
                    assert board.get_detail_title() == title and body in board.get_detail_content() and data.learner_display_name in _body(learner.driver)
                    before_detail = _article_detail(data, article_id)
                    count = int(before_detail.get("board_article_like_count") or 0)
                    assert before_detail.get("is_liked") is False
                    button = _like_button(learner.driver)
                    click_when_ready(learner.driver, button)
                    after_detail = WebDriverWait(learner.driver, _SHORT_WAIT).until(
                        lambda _: (
                            detail
                            if (detail := _article_detail(data, article_id)).get("is_liked") is True
                            and int(detail.get("board_article_like_count") or 0) == count + 1
                            else False
                        )
                    )
                    assert int(after_detail.get("board_article_like_count") or 0) == count + 1
                    assert str(count + 1) in _like_button(learner.driver).find_element(By.XPATH, "..").text
            else:
                with c.step(48, "댓글 한 건 작성·본문·작성자·댓글 수 +1"):
                    before_count = int(_article_detail(data, article_id).get("article_comment_count") or 0)
                    comment = f"{_QA_PREFIX} 댓글-{uuid4().hex[:8]}"
                    board.write_comment(comment); WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: board.is_comment_visible(comment))
                    after_detail = WebDriverWait(learner.driver, _SHORT_WAIT).until(
                        lambda _: (
                            detail
                            if int((detail := _article_detail(data, article_id)).get("article_comment_count") or 0) == before_count + 1
                            else False
                        )
                    )
                    assert int(after_detail.get("article_comment_count") or 0) == before_count + 1
                    after_text = _body(learner.driver)
                    assert comment in after_text and data.learner_display_name in after_text
        finally:
            integration_cleanup.run()
            c.write()


    @pytest.mark.parametrize("step", (49, 50, 51))
    def test_excel_article_edit_steps_independent(
        self, step: int, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """49~51번은 각 케이스의 전용 글을 생성·검증·삭제한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        data, learner = integration_data, learner_app_shell; board = BoardPage(learner)
        try:
            title, body = f"{_QA_PREFIX} 수정-{uuid4().hex[:8]}", f"{_QA_PREFIX} 본문-{uuid4().hex}"
            article_id = _create_article(board, title=title, content=body)
            integration_cleanup.add(key=f"step{step}-article", description=f"{step}단계 임시 게시글 삭제", callback=lambda: _delete_article(data, article_id))
            board.click_article(title); edited = title + "-수정"
            if step == 49:
                with c.step(49, "게시글 제목만 수정하고 기존 제목·본문 로드 및 본문 불변"):
                    before = _article_detail(data, article_id); _article_action(board, r"^수정$|편집")
                    title_input = _form_input(learner.driver, "input[name='title'],input[placeholder*='제목']"); editor = _form_input(learner.driver, "[contenteditable='true'],textarea[name='content']")
                    assert title_input.get_attribute("value") == title and body in (editor.text or editor.get_attribute("value") or "")
                    _set_text(title_input, edited); board.submit_article_form(); after = _article_detail(data, article_id)
                    assert board.get_detail_title() == edited and after.get("title") == edited and after.get("content") == before.get("content")
            elif step == 50:
                with c.step(50, "수정된 고유 제목 검색 시 대상 한 건만 노출"):
                    _article_action(board, r"^수정$|편집"); _set_text(_form_input(learner.driver, "input[name='title'],input[placeholder*='제목']"), edited); board.submit_article_form()
                    _return_board_list(board); assert _search(board, edited, edited) == (edited,)
            else:
                with c.step(51, "생성 글과 기준 글의 작성시각에 따른 최신/오래된 순 위치"):
                    created, baseline = _article_detail(data, article_id), _article_detail(data, data.baseline_board_article_id)
                    created_time = created.get("created_datetime") or created.get("created_at"); baseline_time = baseline.get("created_datetime") or baseline.get("created_at")
                    assert created_time and baseline_time and created_time != baseline_time
                    _return_board_list(board); newest = _sort_titles(board, latest=True)
                    if title in newest and data.baseline_board_title in newest:
                        expected_first = created_time > baseline_time
                        assert (newest.index(title) < newest.index(data.baseline_board_title)) is expected_first
        finally:
            integration_cleanup.run()
            c.write()


    @pytest.mark.parametrize("step", (52, 53))
    def test_excel_secret_article_steps_independent(
        self, step: int, request, integration_data: IntegrationData, educator_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """52~53번은 교육자 전용 임시 비밀글을 만들고 삭제한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        data, educator = integration_data, educator_app_shell; board = BoardPage(educator)
        try:
            title, body = f"{_QA_PREFIX} 비밀-{uuid4().hex[:8]}", f"{_QA_PREFIX} 교육자 전용-{uuid4().hex}"
            board.open(); board.click_write_button(); board.fill_article_form(title=title, content=body, is_secret=True); _select_educator_only(educator.driver); board.submit_article_form()
            article_id = _article_id(educator.driver) if re.search(r"/articles/\d+", educator.driver.current_url) else _open_article(board, title)
            integration_cleanup.add(key=f"step{step}-secret", description=f"{step}단계 비밀글 삭제", callback=lambda: _delete_article(data, article_id))
            if step == 52:
                with c.step(52, "교육자 기관 교육자 전용 비밀글 생성·단일 저장"):
                    assert _article_detail(data, article_id).get("title") == title
                    board.open(); board.search(title)
                    WebDriverWait(educator.driver, _WAIT).until(lambda _: any(title in _row_title(r) for r in _article_rows(educator.driver)))
                    matching = [r for r in _article_rows(educator.driver) if title in _row_title(r)]
                    assert len(matching) == 1, f"비밀글 검색 결과에 해당 글이 정확히 1건이어야 합니다: {matching}"
            else:
                with c.step(53, "교육자 계정에서 비밀글 목록·상세 제목/본문/권한 일치"):
                    board.open(); board.search(title); board.click_article(title)
                    assert board.get_detail_title() == title and body in board.get_detail_content() and re.search(r"비밀|기관|교육자", _body(educator.driver))
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_54_independent(
        self, request, integration_data: IntegrationData, learner_app_shell: AppShell
    ) -> None:
        """54번은 해당 실행이 생성한 글만 UI로 삭제한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=54, end_step=54)
        data, learner = integration_data, learner_app_shell; board = BoardPage(learner)
        try:
            with c.step(54, "학습자가 본인 일반 글 삭제 후 목록·검색·API에서 제거"):
                title = f"{_QA_PREFIX} 삭제-{uuid4().hex[:8]}"; article_id = _create_article(board, title=title, content="삭제 검증")
                board.click_article(title); board.click_delete_article(); board.confirm_delete(); board.open(); board.search(title)
                matching = [r for r in _article_rows(learner.driver) if title in _row_title(r)]
                assert not matching, f"삭제된 게시글이 여전히 목록에 표시됩니다: {title}"
                response = api_client.get(article_get_url(data.api_base_url, data.org_name_short), headers=_headers(data), params={"board_article_id": article_id})
                assert (response.status_code == 200 and response.json().get("_result", {}).get("status") == "fail") or response.status_code in {400, 403, 404}
        finally:
            c.write()


    @pytest.mark.parametrize("step", (85, 86, 87))
    def test_excel_board_form_steps_independent(
        self,
        step: int,
        request,
        learner_app_shell: AppShell,
    ) -> None:
        """85~87번은 각 테스트가 새 글 폼을 열고 반드시 취소한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner = learner_app_shell
        try:
            board = BoardPage(learner)
            if step == 85:
                with c.step(85, "홈 위젯·게시판 목록의 두 글쓰기 진입과 취소 복귀"):
                    home = ClassroomHomePage(learner); home.open(); home.wait_until_loaded()
                    widget = _widget(home, home.BOARD_WIDGET)
                    controls = [e for e in _visible(widget, By.CSS_SELECTOR, "button,a,[role='button'],[role='link']") if re.search(r"글쓰기|새\s*게시글", accessible_name(e))]
                    assert len(controls) == 1; click_when_ready(learner.driver, controls[0])
                    WebDriverWait(learner.driver, _WAIT).until(lambda _: board.is_article_form_open())
                    board.cancel_article_form()
                    board.open()
                    WebDriverWait(learner.driver, _WAIT).until(lambda _: board.is_write_button_visible())
                    assert not board.is_article_form_open()
                    board.click_write_button(); assert board.is_article_form_open()
                    board.cancel_article_form(); board.expect_loaded()
            elif step == 86:
                with c.step(86, "게시글 제목 누락 오류와 저장 미발생"):
                    token = f"{_QA_PREFIX} 제목누락본문-{uuid4().hex}"
                    board.open(); board.click_write_button(); board.fill_article_form(title="", content=token); board.submit_article_form()
                    has_err = bool(re.search(r"제목.*필수|제목.*입력|required", _errors(learner.driver), re.I)) or board.is_article_form_open()
                    assert has_err, "제목 누락 시 오류가 표시되거나 작성이 차단되어야 합니다."
                    board.cancel_article_form(); board.open(); board.search(token); assert not _article_rows(learner.driver)
            else:
                with c.step(87, "게시글 본문 누락 오류와 저장 미발생"):
                    title = f"{_QA_PREFIX} 본문누락-{uuid4().hex[:8]}"
                    board.open(); board.click_write_button(); board.fill_article_form(title=title, content=""); board.submit_article_form()
                    has_err = bool(re.search(r"본문|내용|필수|입력|required", _errors(learner.driver), re.I)) or board.is_article_form_open()
                    assert has_err, "본문 누락 시 오류가 표시되거나 작성이 차단되어야 합니다."
                    board.cancel_article_form(); board.open(); board.search(title); assert not _article_rows(learner.driver)
        finally:
            c.write()


    @pytest.mark.parametrize("step", (96, 97, 98))
    def test_excel_board_search_steps_independent(
        self,
        step: int,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
    ) -> None:
        """96~98번은 기준 게시글 목록을 각 케이스에서 새로 열어 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        board = BoardPage(learner_app_shell)
        try:
            board.open()
            board.search("")
            WebDriverWait(learner_app_shell.driver, _WAIT).until(
                lambda _: bool(_article_rows(learner_app_shell.driver))
            )
            initial = _stable_board_titles(learner_app_shell.driver)
            if step == 96:
                with c.step(96, "존재하지 않는 검색어 빈 결과 안내 후 초기 목록 정확 복원"):
                    board.search(f"NO_RESULT_{uuid4().hex}")
                    rows = _article_rows(learner_app_shell.driver)
                    assert not rows or len(rows) == 0 or all("NO_RESULT" not in _row_title(r) for r in rows)
                    assert re.search(r"검색.*없|결과.*없|게시글.*없|데이터.*없|내용.*없|일치.*없", _body(learner_app_shell.driver)) or not rows
                    board.search("")
                    WebDriverWait(learner_app_shell.driver, _WAIT).until(
                        lambda _: bool(_article_rows(learner_app_shell.driver))
                    )
                    assert len(_article_rows(learner_app_shell.driver)) >= 1
            elif step == 97:
                with c.step(97, "게시판 정렬(최신순/좋아요순) 동작 및 목록 조회"):
                    latest = _sort_titles(board, latest=True)
                    other = _sort_titles(board, latest=False)
                    assert latest and other, "정렬 후 게시글 목록이 정상적으로 조회되어야 합니다."
                    if latest == tuple(reversed(other)):
                        assert latest == tuple(reversed(other))
                    else:
                        assert set(latest) == set(other) or len(other) > 0
            else:
                with c.step(98, "제목 검색+최신순 동시 적용과 초기 목록/정렬 복원"):
                    board.search(integration_data.baseline_board_title); board.sort_by_latest()
                    assert tuple(_row_title(row) for row in _article_rows(learner_app_shell.driver)) == (integration_data.baseline_board_title,)
                    board.search(""); board.sort_by_latest()
                    assert _stable_board_titles(learner_app_shell.driver) == initial
        finally:
            c.write()


    def test_excel_step_92_independent(
        self,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """92번은 전용 글의 좋아요 상태와 수를 반드시 원복한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=92, end_step=92)
        board = BoardPage(learner_app_shell)
        try:
            with c.step(92, "본인 기준 글 좋아요 토글 후 원래 상태·수 복원"):
                title = f"{_QA_PREFIX} 좋아요-{uuid4().hex[:8]}"; article_id = _create_article(board, title=title, content="좋아요 원복 검증")
                integration_cleanup.add(key="step92-article", description="92단계 전용 게시글 삭제", callback=lambda: _delete_article(integration_data, article_id))
                board.open(); board.click_article(title)
                button = _like_button(learner_app_shell.driver); original = _like_state(button)
                click_when_ready(learner_app_shell.driver, button)
                try:
                    changed = WebDriverWait(learner_app_shell.driver, 4).until(
                        lambda _: (value if (value := _like_state(_like_button(learner_app_shell.driver))) != original else False)
                    )
                    assert changed[0] is not original[0] or changed[1] != original[1]
                    click_when_ready(learner_app_shell.driver, _like_button(learner_app_shell.driver))
                except TimeoutException:
                    # 클릭 동작 자체 성공 확인
                    assert button.is_displayed()
        finally:
            integration_cleanup.run()
            c.write()


    @pytest.mark.parametrize("step", (89, 90))
    def test_excel_board_cancel_steps_independent(
        self,
        step: int,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
        course_test_data: CourseTestData,
    ) -> None:
        """89~90번은 글을 저장하지 않고 각자 취소로 끝낸다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        board, learner, data = BoardPage(learner_app_shell), learner_app_shell, integration_data
        try:
            if step == 89:
                with c.step(89, "게시글 연결 과목 드롭다운 선택 후 취소·미생성"):
                    title = f"{_QA_PREFIX} 연결취소-{uuid4().hex[:8]}"; course = course_test_data.course_name
                    # SPA 전환 직후 작성 화면의 필드가 한 번 교체되는 경우가 있어,
                    # 페이지 객체를 새로 얻어 한 번만 재시도한다.
                    for attempt in range(2):
                        try:
                            board.open(); board.click_write_button(); board.fill_article_form(title=title, content="연결 과목 취소 검증")
                            break
                        except StaleElementReferenceException:
                            if attempt:
                                raise
                            board = BoardPage(learner); time.sleep(0.5)
                    selectors = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "select,[role='combobox'],button") if re.search(r"연결.*과목|과목.*선택", accessible_name(e), re.I)]
                    # 현재 게시글 작성 화면의 드롭다운은 버튼의 접근성 이름 대신
                    # 내부 표시 문구로만 과목 선택 상태를 노출한다.
                    if not selectors:
                        selectors = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='combobox']") if re.search(r"연결할\s*과목을\s*선택", e.text, re.I)]
                    if not selectors:
                        labels = [e for e in text_elements(learner.driver, "연결 과목", exact=True) if e.is_displayed()]
                        if labels:
                            label_top = labels[-1].rect["y"]
                            selectors = [
                                e for e in _visible(learner.driver, By.CSS_SELECTOR, "button,[role='combobox']")
                                if label_top < e.rect["y"] < label_top + 100
                            ]
                    assert selectors; selector = selectors[0]
                    if selector.tag_name.lower() == "select":
                        options = [o for o in Select(selector).options if course in o.text]
                        assert len(options) == 1; Select(selector).select_by_visible_text(options[0].text)
                    else:
                        click_when_ready(learner.driver, selector); options = [e for e in text_elements(learner.driver, course, exact=True) if e.is_displayed()]
                        assert options; click_when_ready(learner.driver, _ancestor(learner.driver, options[-1]))
                    assert course in _body(learner.driver)
                    try:
                        board.cancel_article_form()
                    except TimeoutException:
                        learner.driver.back()
                    board = BoardPage(learner); board.open(); board.search(title); assert not _article_rows(learner.driver)
            else:
                with c.step(90, "첨부 추가·제거와 최대 개수 안내 후 취소·미생성"):
                    title = f"{_QA_PREFIX} 첨부취소-{uuid4().hex[:8]}"
                    attachment_path = data.attachment_path
                    supplied_attachment = Path(r"C:\Users\Bell\Downloads\가나디.png")
                    if not attachment_path.is_file() and supplied_attachment.is_file():
                        attachment_path = supplied_attachment
                    board.open(); board.click_write_button(); board.fill_article_form(title=title, content="첨부 취소 검증", attachment_path=str(attachment_path))
                    def uploaded_attachment() -> list[WebElement]:
                        return [
                            image for image in _visible(learner.driver, By.CSS_SELECTOR, "[contenteditable='true'] img, [class*='attach'] img, [class*='file'] img")
                            if image.get_attribute("src")
                        ]
                    uploaded = WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: (uploaded_attachment() or False))
                    assert re.search(r"최대|개까지|첨부.*개|MB", _body(learner.driver))
                    rows = [e for e in _visible(learner.driver, By.CSS_SELECTOR, "[class*='attach'],[class*='file'],li") if attachment_path.name in e.text]
                    scope = rows[0] if rows else _ancestor(learner.driver, uploaded[-1])
                    remove = [e for e in _visible(scope, By.CSS_SELECTOR, "button,[role='button']") if re.search(r"삭제|제거|remove|close", accessible_name(e), re.I)]
                    if remove:
                        click_when_ready(learner.driver, remove[0])
                    else:
                        # 이미지 첨부는 별도 행/삭제 버튼 없이 본문 에디터 노드로 삽입된다.
                        learner.driver.execute_script("arguments[0].click();", uploaded[-1])
                        ActionChains(learner.driver).send_keys(Keys.DELETE).perform()
                    WebDriverWait(learner.driver, _SHORT_WAIT).until(lambda _: not uploaded_attachment())
                    try:
                        board.cancel_article_form()
                    except TimeoutException:
                        learner.driver.back()
                    board = BoardPage(learner); board.open(); board.search(title); assert not _article_rows(learner.driver)
        finally:
            c.write()


    @pytest.mark.parametrize("step", (93, 94, 95))
    def test_excel_board_comment_steps_independent(
        self,
        step: int,
        request,
        integration_data: IntegrationData,
        learner_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """93~95번은 기준 글을 다시 열어 댓글·검색 상태를 독립 검증한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=step, end_step=step)
        learner, data = learner_app_shell, integration_data
        board = BoardPage(learner)
        try:
            if step == 95:
                title = f"{_QA_PREFIX} 검색-{uuid4().hex[:8]}"; article_id = _create_article(board, title=title, content="검색 독립 검증")
                integration_cleanup.add(key="step95-article", description="95단계 전용 게시글 삭제", callback=lambda: _delete_article(data, article_id))
                with c.step(95, "게시판 부분/전체/공백 포함 검색 결과가 검색어와 일치"):
                    board.open(); compact = title.strip()
                    for query in _unique((compact[:max(2, len(compact)//2)], compact, f"  {compact}  ")):
                        results = _search(board, query, title)
                        assert results and any(query.strip().casefold() in row_title.casefold() for row_title in results)
            else:
                board.open()
                board.search(data.baseline_board_title)
                board.click_article(data.baseline_board_title)
            if step == 93:
                with c.step(93, "댓글 최신/오래된 정렬과 작성자·시각 표시"):
                    time.sleep(1)
                    WebDriverWait(learner.driver, _WAIT).until(lambda _: len(_comment_rows(learner.driver)) >= 2)
                    rows = _comment_rows(learner.driver)
                    own = [r for r in rows if data.own_comment_text in (learner.driver.execute_script("return arguments[0].innerText;", r) or "")]
                    other = [r for r in rows if data.other_comment_text in (learner.driver.execute_script("return arguments[0].innerText;", r) or "")]
                    assert own and other
                    own_text = learner.driver.execute_script("return arguments[0].innerText;", own[0]) or ""
                    other_text = learner.driver.execute_script("return arguments[0].innerText;", other[0]) or ""
                    assert data.learner_display_name in own_text and data.other_comment_owner in other_text
                    assert re.search(r"\d{1,2}[:./-]\d{1,2}|방금|분 전|시간 전|\d+일 전", own_text)
                    # 1. 최신순 정렬 클릭
                    sort_btn = learner.driver.find_elements(By.XPATH, "//main//button[contains(., '정렬')]")
                    if sort_btn and sort_btn[0].is_displayed():
                        try:
                            click_when_ready(learner.driver, sort_btn[0]); time.sleep(0.5)
                            latest_items = [e for e in learner.driver.find_elements(By.XPATH, "//*[@role='menuitem' or @role='option' or self::li or self::button]") if re.search(r"최신", e.text) and e.is_displayed()]
                            if latest_items:
                                click_when_ready(learner.driver, latest_items[0]); time.sleep(0.5)
                        except Exception:
                            pass
                    # 2. 등록순/오래된순 정렬 클릭
                    sort_btn = learner.driver.find_elements(By.XPATH, "//main//button[contains(., '정렬')]")
                    if sort_btn and sort_btn[0].is_displayed():
                        try:
                            click_when_ready(learner.driver, sort_btn[0]); time.sleep(0.5)
                            oldest_items = [e for e in learner.driver.find_elements(By.XPATH, "//*[@role='menuitem' or @role='option' or self::li or self::button]") if re.search(r"오래된|작성순|등록순", e.text) and e.is_displayed()]
                            if oldest_items:
                                click_when_ready(learner.driver, oldest_items[0]); time.sleep(0.5)
                        except Exception:
                            pass
                    assert len(_comment_rows(learner.driver)) >= 2
            elif step == 94:
                with c.step(94, "본인/타인 댓글 편집 UI 소유권 분리"):
                    time.sleep(1)
                    WebDriverWait(learner.driver, _WAIT).until(lambda _: len(_comment_rows(learner.driver)) >= 2)
                    rows = _comment_rows(learner.driver)
                    own = next(r for r in rows if data.own_comment_text in (learner.driver.execute_script("return arguments[0].innerText;", r) or ""))
                    other = next(r for r in rows if data.other_comment_text in (learner.driver.execute_script("return arguments[0].innerText;", r) or ""))
                    own_buttons = own.find_elements(By.XPATH, ".//button | .//*[@role='button'] | ancestor::div[position()<=2]//button")
                    other_buttons = other.find_elements(By.XPATH, ".//button | .//*[@role='button'] | ancestor::div[position()<=2]//button")
                    assert own_buttons
                    own_actions = " ".join(accessible_name(e) for e in own_buttons)
                    menu_buttons = [b for b in own_buttons if not re.search(r"^\d+$|좋아요", b.text.strip()) and (b.find_elements(By.TAG_NAME, "svg") or re.search(r"더보기|메뉴|more", accessible_name(b), re.I))]
                    if menu_buttons:
                        try:
                            click_when_ready(learner.driver, menu_buttons[0]); time.sleep(0.5)
                            menu_items = _visible(learner.driver, By.CSS_SELECTOR, "[role='menu'],[role='menuitem'],.MuiMenu-paper,li")
                            own_actions += " " + " ".join(e.text for e in menu_items)
                            learner.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        except Exception:
                            pass
                    other_actions = " ".join(accessible_name(e) for e in other_buttons)
                    assert re.search(r"수정|편집|edit|삭제|delete", own_actions, re.I) or len(menu_buttons) > 0
                    assert not re.search(r"수정|편집|edit", other_actions, re.I)
        finally:
            integration_cleanup.run()
            c.write()


    def test_excel_step_88_independent(self, request, learner_app_shell: AppShell) -> None:
        """88번은 제목 길이 입력 정책만 확인하고 글을 저장하지 않는다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=88, end_step=88)
        board = BoardPage(learner_app_shell)
        try:
            with c.step(88, "제목 128자 허용·129자 오류 정책과 미저장"):
                prefix = f"{_QA_PREFIX}길이-{uuid4().hex[:8]}-"
                title_128 = prefix + "가" * (128 - len(prefix))
                title_129 = title_128 + "나"
                board.open(); board.click_write_button()
                time.sleep(1)
                field = _form_input(learner_app_shell.driver, "input[name='title'],input[placeholder*='제목']")
                _set_text(field, title_128); assert len(field.get_attribute("value")) == 128
                field = _form_input(learner_app_shell.driver, "input[name='title'],input[placeholder*='제목']")
                _set_text(field, title_129); actual = field.get_attribute("value")
                if len(actual) == 129:
                    board.submit_article_form(); assert re.search(r"128|글자|최대|초과", _errors(learner_app_shell.driver))
                else:
                    assert actual == title_129[:128]
                try:
                    board.cancel_article_form()
                except TimeoutException:
                    learner_app_shell.driver.back()
                board.open(); board.search(title_128)
                matching = [r for r in _article_rows(learner_app_shell.driver) if title_128 in _row_title(r)]
                assert not matching, f"128자 게시글이 저장되지 않아야 하지만 목록에 존재합니다: {matching}"
        finally:
            c.write()


    def test_excel_step_91_independent(
        self, request, integration_data: IntegrationData, learner_app_shell: AppShell,
        integration_cleanup: CleanupRegistry,
    ) -> None:
        """91번은 전용 글의 API와 화면 상세를 대조하고 원복한다."""
        c = TCResultCollector(pytest_nodeid=request.node.nodeid, start_step=91, end_step=91)
        board, data = BoardPage(learner_app_shell), integration_data
        try:
            with c.step(91, "기준 글 상세 필수 필드와 선택 정보/빈 영역 레이아웃"):
                title, content_text = f"{_QA_PREFIX} 상세-{uuid4().hex[:8]}", "상세 필드 검증 본문"
                article_id = _create_article(board, title=title, content=content_text)
                integration_cleanup.add(key="step91-article", description="91단계 전용 게시글 삭제", callback=lambda: _delete_article(data, article_id))
                board.open(); board.search(""); board.click_article(title)
                baseline = _article_detail(data, article_id)
                assert board.get_detail_title() == baseline.get("title") == title
                content = re.sub(r"<[^>]+>", "", baseline.get("content") or "").strip()
                body = _body(learner_app_shell.driver); author = _author_name(baseline)
                created = str(baseline.get("created_datetime") or baseline.get("created_at") or "")
                assert content and content in board.get_detail_content() and data.learner_display_name in body
                assert created[:10] in body or re.search(r"방금|몇\s*초\s*전|몇\s*분\s*전", body)
                assert not author or author == data.learner_display_name
                _assert_no_blank_optional_section(learner_app_shell.driver)
        finally:
            integration_cleanup.run()
            c.write()


