"""현재 QA6 Part2 저부하 테스트의 하드 리밋과 JMX 안전장치를 검증한다."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree
import pytest

from part2_performance.scripts.build_comparison_report import collect
from part2_performance.scripts.run_lecture_load import _validate_csv, _validate_jmx_structure, _validate_limits
from part2_performance.scripts.summarize_results import extract_summary

ROOT = Path(__file__).resolve().parents[1]
JMX = ROOT / "jmeter" / "lecture_test_cycle.jmx"

def _args(**overrides) -> argparse.Namespace:
    values = {"confirm_approved_window": True, "users": 5, "rampup": 90, "loops": 3}
    values.update(overrides)
    return argparse.Namespace(**values)

@pytest.mark.parametrize(("override", "message"), [
    ({"rampup": 89}, "90~120초"),
    ({"rampup": 121}, "90~120초"),
    ({"loops": 4}, "하드 리밋 3회"),
    ({"confirm_approved_window": False}, "--confirm-approved-window"),
])
def test_limits_fail_closed(override: dict, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        _validate_limits(_args(**override))

def test_limits_accept_current_load_and_smoke_values() -> None:
    assert _validate_limits(_args()) == 90
    assert _validate_limits(_args(users=1, rampup=1, loops=3)) == 1
    # 특정 단계 재검증을 허용하므로 이전 단계 실행 기록은 요구하지 않는다.
    assert _validate_limits(_args(users=20, rampup=90, loops=3)) == 90

def test_accounts_csv_requires_30_unique_accounts() -> None:
    with TemporaryDirectory() as temp_dir:
        account_csv = Path(temp_dir) / "accounts.csv"
        rows = ["login_id,password"] + [f"qa{index:02d}@example.com,pw{index}" for index in range(30)]
        account_csv.write_text("\n".join(rows) + "\n", encoding="utf-8")
        assert _validate_csv(account_csv, 30) == account_csv.resolve()
        rows[-1] = "qa00@example.com,different-password"
        account_csv.write_text("\n".join(rows) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="중복 login_id"):
            _validate_csv(account_csv, 30)

def test_jmx_contains_current_hard_limits_and_exact_flow() -> None:
    _validate_jmx_structure(JMX)
    root = ElementTree.parse(JMX).getroot()
    paths = [node.text for node in root.findall(".//stringProp[@name='HTTPSampler.path']")]
    assert paths == [
        "/login/pw",
        "/org/academy/course/get/",
        "/org/academy/user/lecture/test/enter/",
        "/org/academy/user/lecture/test/start/",
        "/org/academy/user/lecture/test/stop/",
        "/org/academy/lecture/test/reset/by_self/",
    ]
    timers = root.findall(".//UniformRandomTimer")
    assert len(timers) == 4
    assert all(timer.findtext("stringProp[@name='ConstantTimer.delay']") == "3000" and timer.findtext("stringProp[@name='RandomTimer.range']") == "2000" for timer in timers)
    assert all(timeout.text == "60000" for timeout in root.findall(".//stringProp[@name='HTTPSampler.response_timeout']"))
    view_tree = root.find(".//ResultCollector[@testname='View Results Tree']")
    assert view_tree is not None and view_tree.get("enabled") == "false"

def test_jmx_dev_target_validation_rejects_wrong_course() -> None:
    with TemporaryDirectory() as temp_dir:
        altered = Path(temp_dir) / "altered.jmx"
        text = JMX.read_text(encoding="utf-8").replace(
            '<stringProp name="Argument.value">727</stringProp>',
            '<stringProp name="Argument.value">999</stringProp>', 1,
        )
        altered.write_text(text, encoding="utf-8")
        with pytest.raises(SystemExit, match="course_id"):
            _validate_jmx_structure(altered)

def test_summary_uses_current_completion_latency_and_error_rules() -> None:
    statistics = {"Total": {"sampleCount": 17, "meanResTime": 300, "maxResTime": 900, "pct1ResTime": 400, "pct2ResTime": 500, "pct3ResTime": 600, "throughput": 1.0, "errorPct": 0.0}}
    base = {"samples": 15, "average_latency_ms": 4999.0, "p95_latency_ms": 500.0, "p99_latency_ms": 600.0, "average_response_ms": 300.0, "p95_response_ms": 500.0, "p99_response_ms": 600.0, "throughput_rps": 1.0, "error_percent": 0.99}
    integrity = {"complete": True, "errors": [], "expected_total_samples": 17, "actual_total_samples": 17, "scenario_expected_per_label": 3}
    assert extract_summary(statistics, 1, 3, integrity=integrity, scenario_metrics=base)["status"] == "PASS"
    assert extract_summary(statistics, 1, 3, integrity=integrity, scenario_metrics={**base, "average_latency_ms": 5000.0})["status"] == "FAIL"
    assert extract_summary(statistics, 1, 3, integrity=integrity, scenario_metrics={**base, "error_percent": 1.0})["status"] == "FAIL"
    assert extract_summary(statistics, 1, 3, integrity={**integrity, "complete": False, "errors": ["incomplete"]}, scenario_metrics=base)["status"] == "INVALID"

def test_comparison_report_accepts_current_summary_schema() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        report = root / "lecture-cycle-5u-3loop-test" / "report"
        report.mkdir(parents=True)
        summary = {
            "status": "PASS", "execution_complete": True, "users": 5, "loops": 3, "samples": 75,
            "average_latency_ms": 200.0, "p95_latency_ms": 300.0, "p99_latency_ms": 350.0,
            "average_response_ms": 250.0, "p95_response_ms": 350.0, "p99_response_ms": 400.0,
            "throughput_rps": 1.2, "error_percent": 0.0,
        }
        (report / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        rows = collect(root)
        assert len(rows) == 1
        assert rows[0]["average_latency_ms"] == 200.0
