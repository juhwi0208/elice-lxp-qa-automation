"""JMeter Dashboard를 QA6 Part2 기준으로 요약하고 실행 완전성까지 검증한다."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SUCCESS_ERROR_PCT = 1.0
SUCCESS_AVG_MS = 5_000.0
SCENARIO_LABELS = [
    "01_GET_course_info",
    "02_POST_test_enter",
    "03_POST_test_start",
    "04_POST_test_stop",
    "05_POST_test_reset",
]
ONCE_LABELS = ["00_SAFETY_GUARD", "00_AUTH_login"]
METRIC_FIELDS = {
    "samples": "sampleCount",
    "average_ms": "meanResTime",
    "p90_ms": "pct1ResTime",
    "p95_ms": "pct2ResTime",
    "p99_ms": "pct3ResTime",
    "throughput_rps": "throughput",
    "error_percent": "errorPct",
}


def _extract_metrics(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for output_name, source_name in METRIC_FIELDS.items():
        value = row.get(source_name)
        if not isinstance(value, (int, float)):
            raise ValueError(f"{source_name} 지표가 없거나 숫자가 아닙니다.")
        result[output_name] = round(value, 3) if isinstance(value, float) else value
    return result


def _percentile(values: list[int], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[lower])
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _scenario_metrics_from_jtl(jtl_path: Path) -> dict[str, Any]:
    """성능 판정용 지표를 실제 시험 시나리오 샘플만 대상으로 계산한다.

    00_SAFETY_GUARD와 00_AUTH_login은 부하 시나리오 성능지표에서 제외한다.
    평균 Latency는 JTL의 Latency 컬럼(TTFB)을 사용한다.
    """
    if not jtl_path.is_file():
        raise FileNotFoundError(f"JTL 파일이 없습니다: {jtl_path}")

    latencies: list[int] = []
    elapsed_values: list[int] = []
    start_times: list[int] = []
    end_times: list[int] = []
    failures = 0

    with jtl_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"label", "timeStamp", "elapsed", "Latency", "success"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("JTL에 label/timeStamp/elapsed/Latency/success 컬럼이 필요합니다.")

        for row in reader:
            if row.get("label") not in SCENARIO_LABELS:
                continue
            try:
                ts = int(row["timeStamp"])
                elapsed = int(row["elapsed"])
                latency = int(row["Latency"])
            except (TypeError, ValueError) as exc:
                raise ValueError("JTL 성능지표 컬럼에 숫자가 아닌 값이 있습니다.") from exc
            start_times.append(ts)
            end_times.append(ts + elapsed)
            elapsed_values.append(elapsed)
            latencies.append(latency)
            if str(row.get("success", "")).lower() != "true":
                failures += 1

    if not latencies:
        raise ValueError("JTL에 시험 시나리오 샘플이 없습니다.")

    count = len(latencies)
    duration_seconds = max((max(end_times) - min(start_times)) / 1000.0, 0.001)
    return {
        "samples": count,
        "average_latency_ms": round(sum(latencies) / count, 3),
        "p95_latency_ms": round(_percentile(latencies, 0.95) or 0.0, 3),
        "p99_latency_ms": round(_percentile(latencies, 0.99) or 0.0, 3),
        "average_response_ms": round(sum(elapsed_values) / count, 3),
        "p95_response_ms": round(_percentile(elapsed_values, 0.95) or 0.0, 3),
        "p99_response_ms": round(_percentile(elapsed_values, 0.99) or 0.0, 3),
        "throughput_rps": round(count / duration_seconds, 3),
        "error_percent": round(failures * 100.0 / count, 3),
    }


def _validate_jtl_integrity(jtl_path: Path, users: int, loops: int) -> dict[str, Any]:
    """users × loops가 실제로 전 Thread에서 완주했는지 JTL 원본으로 검증한다."""
    if not jtl_path.is_file():
        return {
            "complete": False,
            "errors": [f"JTL 파일이 없습니다: {jtl_path}"],
            "expected_total_samples": users * (len(ONCE_LABELS) + len(SCENARIO_LABELS) * loops),
            "actual_total_samples": None,
            "scenario_expected_per_label": users * loops,
        }

    label_counts: Counter[str] = Counter()
    label_threads: dict[str, Counter[str]] = defaultdict(Counter)
    total_rows = 0

    with jtl_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"label", "threadName", "success"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            return {
                "complete": False,
                "errors": ["JTL에 label/threadName/success 컬럼이 없습니다."],
                "expected_total_samples": users * (len(ONCE_LABELS) + len(SCENARIO_LABELS) * loops),
                "actual_total_samples": None,
                "scenario_expected_per_label": users * loops,
            }

        for row in reader:
            total_rows += 1
            label = row.get("label", "")
            thread_name = row.get("threadName", "")
            label_counts[label] += 1
            if thread_name:
                label_threads[label][thread_name] += 1

    errors: list[str] = []
    expected_per_scenario = users * loops

    for label in ONCE_LABELS:
        actual = label_counts[label]
        if actual != users:
            errors.append(f"{label}: expected {users} samples, actual {actual}")
        threads = label_threads[label]
        if len(threads) != users:
            errors.append(f"{label}: expected {users} unique threads, actual {len(threads)}")
        bad = {name: count for name, count in threads.items() if count != 1}
        if bad:
            errors.append(f"{label}: thread별 1회 실행 위반 {bad}")

    for label in SCENARIO_LABELS:
        actual = label_counts[label]
        if actual != expected_per_scenario:
            errors.append(f"{label}: expected {expected_per_scenario} samples, actual {actual}")
        threads = label_threads[label]
        if len(threads) != users:
            errors.append(f"{label}: expected {users} unique threads, actual {len(threads)}")
        bad = {name: count for name, count in threads.items() if count != loops}
        if bad:
            errors.append(f"{label}: thread별 {loops}회 실행 위반 {bad}")

    expected_total = users * (len(ONCE_LABELS) + len(SCENARIO_LABELS) * loops)
    if total_rows != expected_total:
        errors.append(f"Total samples: expected {expected_total}, actual {total_rows}")

    return {
        "complete": not errors,
        "errors": errors,
        "expected_total_samples": expected_total,
        "actual_total_samples": total_rows,
        "scenario_expected_per_label": expected_per_scenario,
    }


def extract_summary(
    statistics: dict[str, Any],
    users: int,
    loops: int,
    *,
    integrity: dict[str, Any] | None = None,
    scenario_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dashboard statistics에서 전체/단계별 지표와 실행 완전성을 추출한다."""
    total = statistics.get("Total")
    if not isinstance(total, dict):
        raise ValueError("statistics.json에 Total 통계가 없습니다.")

    dashboard_total = _extract_metrics(total)
    execution_complete = True if integrity is None else bool(integrity["complete"])

    if scenario_metrics is None:
        # 하위 호환용. 실제 실행에서는 JTL 기반 scenario_metrics를 반드시 전달한다.
        performance = {
            "samples": dashboard_total["samples"],
            "average_latency_ms": dashboard_total["average_ms"],
            "p95_latency_ms": dashboard_total["p95_ms"],
            "p99_latency_ms": dashboard_total["p99_ms"],
            "average_response_ms": dashboard_total["average_ms"],
            "p95_response_ms": dashboard_total["p95_ms"],
            "p99_response_ms": dashboard_total["p99_ms"],
            "throughput_rps": dashboard_total["throughput_rps"],
            "error_percent": dashboard_total["error_percent"],
        }
    else:
        performance = scenario_metrics

    if not execution_complete:
        status = "INVALID"
    elif performance["error_percent"] < SUCCESS_ERROR_PCT and performance["average_latency_ms"] < SUCCESS_AVG_MS:
        status = "PASS"
    else:
        status = "FAIL"

    summary: dict[str, Any] = {
        "status": status,
        "execution_complete": execution_complete,
        "integrity_errors": [] if integrity is None else integrity["errors"],
        "users": users,
        "loops": loops,
        **performance,
        "dashboard_total": dashboard_total,
        "success_rule": "complete users×loops execution AND scenario error_rate < 1% AND scenario average Latency < 5000ms",
        "transactions": [],
    }
    if integrity is not None:
        summary.update(
            expected_total_samples=integrity["expected_total_samples"],
            actual_total_samples=integrity["actual_total_samples"],
            scenario_expected_per_label=integrity["scenario_expected_per_label"],
        )

    for label in SCENARIO_LABELS:
        row = statistics.get(label)
        if isinstance(row, dict):
            summary["transactions"].append({"label": label, **_extract_metrics(row)})
        else:
            summary["transactions"].append(
                {
                    "label": label,
                    "samples": 0,
                    "average_ms": None,
                    "p90_ms": None,
                    "p95_ms": None,
                    "p99_ms": None,
                    "throughput_rps": None,
                    "error_percent": None,
                }
            )
    return summary


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _write_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    fieldnames = [
        "status", "execution_complete", "users", "loops", "samples",
        "expected_total_samples", "actual_total_samples", "average_latency_ms",
        "p95_latency_ms", "p99_latency_ms", "average_response_ms",
        "p95_response_ms", "p99_response_ms", "throughput_rps", "error_percent",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({key: summary.get(key) for key in fieldnames})


def _write_transactions_csv(path: Path, summary: dict[str, Any]) -> None:
    fieldnames = [
        "label", "samples", "average_ms", "p90_ms", "p95_ms", "p99_ms",
        "throughput_rps", "error_percent",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary["transactions"])


def _write_summary_html(path: Path, summary: dict[str, Any], dashboard_relative: str = "index.html") -> None:
    status_class = "pass" if summary["status"] == "PASS" else "fail"
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(tx['label'])}</td>"
        f"<td>{_fmt(tx['samples'])}</td>"
        f"<td>{_fmt(tx['average_ms'])}</td>"
        f"<td>{_fmt(tx['p95_ms'])}</td>"
        f"<td>{_fmt(tx['p99_ms'])}</td>"
        f"<td>{_fmt(tx['throughput_rps'])}</td>"
        f"<td>{_fmt(tx['error_percent'])}</td>"
        "</tr>"
        for tx in summary["transactions"]
    )
    integrity_note = "실행 완전성 검증: 정상"
    if not summary["execution_complete"]:
        escaped = "<br>".join(html.escape(message) for message in summary["integrity_errors"])
        integrity_note = f"<strong>실행 불완전(INVALID)</strong><br>{escaped}"

    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QA6 Part2 Load Test Summary</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:32px;line-height:1.45;background:#f7f8fa;color:#17191c}}
main{{max-width:1180px;margin:auto}} .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}}
.card{{background:white;border:1px solid #e4e7eb;border-radius:12px;padding:16px}} .value{{font-size:24px;font-weight:700;margin-top:6px}}
.badge{{display:inline-block;padding:6px 12px;border-radius:999px;font-weight:700}} .pass{{background:#e7f8ec;color:#146b2d}} .fail{{background:#fdecec;color:#a51d1d}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:12px;overflow:hidden}} th,td{{padding:11px 12px;border-bottom:1px solid #eceff2;text-align:right}} th:first-child,td:first-child{{text-align:left}} th{{background:#f0f2f5}}
a{{color:#2457d6}} .note{{background:#fff8dc;border:1px solid #f0df98;padding:14px;border-radius:10px;margin:16px 0}}
</style></head><body><main>
<h1>QA6 Part2 시험 응시 저부하 테스트</h1>
<p><span class="badge {status_class}">{summary['status']}</span> &nbsp; {summary['users']} users / {summary['loops']} loop(s)</p>
<div class="cards">
<div class="card">평균 Latency<div class="value">{_fmt(summary['average_latency_ms'])} ms</div></div>
<div class="card">P95<div class="value">{_fmt(summary['p95_latency_ms'])} ms</div></div>
<div class="card">P99<div class="value">{_fmt(summary['p99_latency_ms'])} ms</div></div>
<div class="card">TPS<div class="value">{_fmt(summary['throughput_rps'])}</div></div>
<div class="card">Error Rate<div class="value">{_fmt(summary['error_percent'])}%</div></div>
</div>
<div class="note">성공 기준: users×loops 실행 완전성 충족, Error Rate &lt; 1%, 평균 Latency &lt; 5,000ms.</div>
<div class="note">{integrity_note}</div>
<h2>API 단계별 지표</h2>
<table><thead><tr><th>Transaction</th><th>Samples</th><th>Avg(ms)</th><th>P95(ms)</th><th>P99(ms)</th><th>TPS</th><th>Error(%)</th></tr></thead><tbody>{rows}</tbody></table>
<p style="margin-top:20px"><a href="{html.escape(dashboard_relative)}">JMeter 원본 HTML Dashboard 열기 →</a></p>
</main></body></html>"""
    path.write_text(doc, encoding="utf-8")


def summarize_report(report_dir: Path, users: int, loops: int, *, run_dir: Path | None = None) -> dict[str, Any]:
    """리포트에서 요약을 만들고 JTL이 있으면 실행 완전성을 강제 검증한다."""
    statistics_path = report_dir / "statistics.json"
    if not statistics_path.is_file():
        raise FileNotFoundError(f"JMeter 통계 파일이 없습니다: {statistics_path}")

    statistics = json.loads(statistics_path.read_text(encoding="utf-8"))
    integrity = None
    scenario_metrics = None
    if run_dir is not None:
        jtl_path = run_dir / "samples.jtl"
        integrity = _validate_jtl_integrity(jtl_path, users, loops)
        scenario_metrics = _scenario_metrics_from_jtl(jtl_path)

    summary = extract_summary(
        statistics, users, loops, integrity=integrity, scenario_metrics=scenario_metrics
    )
    (report_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_summary_csv(report_dir / "summary.csv", summary)
    _write_transactions_csv(report_dir / "transactions.csv", summary)
    _write_summary_html(report_dir / "summary.html", summary)

    if run_dir is not None:
        meta = {
            "users": users,
            "loops": loops,
            "status": summary["status"],
            "execution_complete": summary["execution_complete"],
            "integrity_errors": summary["integrity_errors"],
            "report": str((report_dir / "summary.html").resolve()),
        }
        (run_dir / "run_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_dir", type=Path)
    parser.add_argument("--users", type=int, required=True)
    parser.add_argument("--loops", type=int, required=True)
    parser.add_argument("--run-dir", type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = summarize_report(args.report_dir, args.users, args.loops, run_dir=args.run_dir)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
