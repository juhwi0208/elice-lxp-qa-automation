"""분리된 E2E 테스트의 TCResultCollector 연결 상태를 정적으로 검증한다."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


DEFAULT_TEST_FILES = (
    Path("part3_e2e/tests/e2e_integration/test_01_home_steps.py"),
    Path("part3_e2e/tests/e2e_integration/test_02_course_steps.py"),
    Path("part3_e2e/tests/e2e_integration/test_03_schedule_steps.py"),
    Path("part3_e2e/tests/e2e_integration/test_04_board_steps.py"),
)
EXCLUDED_STEPS = {12, 14, 68}
EXPECTED_STEPS = set(range(1, 99)) - EXCLUDED_STEPS


def _tc_result_steps(source: str) -> list[int]:
    tree = ast.parse(source)
    steps: list[int] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if "independent" not in node.name:
            continue

        collector_names: set[str] = set()
        for child in ast.walk(node):
            if not isinstance(child, ast.Assign):
                continue
            if not isinstance(child.value, ast.Call):
                continue
            constructor = child.value.func
            if not (isinstance(constructor, ast.Name) and constructor.id == "TCResultCollector"):
                continue
            for target in child.targets:
                if isinstance(target, ast.Name):
                    collector_names.add(target.id)

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "step"
                and isinstance(func.value, ast.Name)
                and func.value.id in collector_names
            ):
                continue
            if not child.args:
                continue
            arg = child.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                steps.append(arg.value)

    return steps


def main() -> int:
    missing_files = [path for path in DEFAULT_TEST_FILES if not path.is_file()]
    if missing_files:
        rendered = ", ".join(str(path) for path in missing_files)
        raise FileNotFoundError(f"E2E 분리 테스트 파일이 없습니다: {rendered}")

    steps: list[int] = []
    for path in DEFAULT_TEST_FILES:
        steps.extend(_tc_result_steps(path.read_text(encoding="utf-8")))

    step_set = set(steps)
    missing = sorted(EXPECTED_STEPS - step_set)
    extra = sorted(step_set - EXPECTED_STEPS)
    duplicates = sorted(step for step in step_set if steps.count(step) > 1)

    print("=" * 80)
    print("[E2E TCResultCollector Instrumentation Validation]")
    print("=" * 80)
    print(f"Test files checked    : {len(DEFAULT_TEST_FILES)}")
    print(f"collector.step count  : {len(steps)}")
    print(f"Expected TC count     : {len(EXPECTED_STEPS)}")
    print(f"Excluded steps        : {sorted(EXCLUDED_STEPS)}")
    print(f"Missing steps         : {len(missing)}")
    print(f"Unexpected steps      : {len(extra)}")
    print(f"Duplicate steps       : {len(duplicates)}")

    if missing:
        preview = ", ".join(f"{step:02d}" for step in missing[:20])
        suffix = " ..." if len(missing) > 20 else ""
        print(f"[ERROR] tc_results.step 누락: {preview}{suffix}")

    if extra:
        print("[ERROR] 제외 또는 범위 밖 단계가 기록됩니다: " + ", ".join(map(str, extra)))

    if duplicates:
        print("[ERROR] 둘 이상의 독립 테스트가 같은 단계를 기록합니다: " + ", ".join(map(str, duplicates)))

    if missing or extra or duplicates:
        print("[BLOCK] E2E Sheet/Jira 연동을 활성화하면 안 됩니다.")
        return 1

    print("[OK] 실행 대상 95개 TC가 독립 collector.step으로 연결되어 있습니다.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("=" * 80)
        print("[ERROR] E2E instrumentation validation failed")
        print("=" * 80)
        print(str(exc))
        print("=" * 80)
        sys.exit(1)
