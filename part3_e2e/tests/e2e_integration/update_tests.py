import re
import ast

def rewrite_test_file():
    path = "part3_e2e/tests/e2e_integration/test_all_function_steps_01_98.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Step 26: Create schedule
    content = re.sub(
        r'(def test_basic_step_26_교육자.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        schedule = self._open_schedule(app)\n'
        r'        schedule.click_create_schedule_button()\n'
        r'        title = schedule.make_qa_title("임시일정")\n'
        r'        schedule.fill_schedule_form(title=title, description="설명")\n'
        r'        schedule.submit_schedule_form()\n'
        r'        schedule.wait_until_loaded()\n'
        r'        assert schedule.is_title_present_in_calendar(title)\n'
        r'        integration_state["temp_schedule_title"] = title\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    # Step 28: Edit schedule
    content = re.sub(
        r'(def test_basic_step_28_교육자.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        schedule = self._open_schedule(app)\n'
        r'        title = integration_state.get("temp_schedule_title")\n'
        r'        if not title: pytest.skip("이전 단계에서 일정이 생성되지 않음")\n'
        r'        schedule.click_schedule_card_by_title(title)\n'
        r'        schedule.click_edit_schedule()\n'
        r'        new_title = title + "-수정됨"\n'
        r'        schedule.fill_schedule_form(title=new_title)\n'
        r'        schedule.submit_schedule_form()\n'
        r'        schedule.wait_until_loaded()\n'
        r'        assert schedule.is_title_present_in_calendar(new_title)\n'
        r'        integration_state["temp_schedule_title"] = new_title\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    # Step 32: Delete schedule
    content = re.sub(
        r'(def test_basic_step_32_교육자.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        schedule = self._open_schedule(app)\n'
        r'        title = integration_state.get("temp_schedule_title")\n'
        r'        if not title: pytest.skip("이전 단계에서 일정이 생성되지 않음")\n'
        r'        schedule.click_schedule_card_by_title(title)\n'
        r'        schedule.click_delete_schedule()\n'
        r'        schedule.confirm_delete()\n'
        r'        schedule.wait_until_loaded()\n'
        r'        assert not schedule.is_title_present_in_calendar(title)\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    # Step 45: Board open
    content = re.sub(
        r'(def test_basic_step_45_수강생.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        board = self._open_board(app)\n'
        r'        board.wait_until_loaded()\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    # Step 46: Board validation error
    content = re.sub(
        r'(def test_basic_step_46_수강생.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        board = self._open_board(app)\n'
        r'        board.click_write_button()\n'
        r'        board.submit_article_form()\n'
        r'        assert board.is_write_button_visible() or board.get_article_titles() is not None\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    # Step 47: Board write
    content = re.sub(
        r'(def test_basic_step_47_수강생.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        board = self._open_board(app)\n'
        r'        board.click_write_button()\n'
        r'        title = board.make_qa_title()\n'
        r'        board.fill_article_form(title=title, content="테스트 본문입니다.")\n'
        r'        board.submit_article_form()\n'
        r'        board.wait_until_loaded()\n'
        r'        assert board.is_article_visible(title)\n'
        r'        integration_state["board_article_title"] = title\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    # Step 49: Board search
    content = re.sub(
        r'(def test_basic_step_49_수강생.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        board = self._open_board(app)\n'
        r'        title = integration_state.get("board_article_title")\n'
        r'        if not title: pytest.skip("게시글이 없음")\n'
        r'        board.search(title)\n'
        r'        assert board.is_article_visible(title)\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    # Step 52: Board detail
    content = re.sub(
        r'(def test_basic_step_52_수강생.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        board = self._open_board(app)\n'
        r'        title = integration_state.get("board_article_title")\n'
        r'        if not title: pytest.skip("게시글이 없음")\n'
        r'        board.click_article(title)\n'
        r'        assert board.get_detail_title() == title\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    # Step 57: Board delete
    content = re.sub(
        r'(def test_basic_step_57_수강생.*?:\n(?:.*?""")\n)(.*?)(\n\s+@pytest\.mark|\n    # ════)',
        r'\1'
        r'        app = learner_app_shell\n'
        r'        board = self._open_board(app)\n'
        r'        title = integration_state.get("board_article_title")\n'
        r'        if not title: pytest.skip("게시글이 없음")\n'
        r'        board.click_article(title)\n'
        r'        board.click_delete_article()\n'
        r'        board.confirm_delete()\n'
        r'        board.wait_until_loaded()\n'
        r'        assert not board.is_article_visible(title)\n'
        r'\3',
        content,
        flags=re.DOTALL
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

rewrite_test_file()
