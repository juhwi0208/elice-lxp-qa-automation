"""여러 JMeter 실행 결과를 현재 summary.json 스키마로 비교한다."""
from __future__ import annotations
import argparse, csv, html, json, os
from pathlib import Path
from typing import Any

FIELDS = [
    "status", "execution_complete", "users", "loops", "samples",
    "average_latency_ms", "p95_latency_ms", "p99_latency_ms",
    "average_response_ms", "p95_response_ms", "p99_response_ms",
    "throughput_rps", "error_percent", "run",
]
REQUIRED_FIELDS = set(FIELDS) - {"run"}

def collect(results_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(results_root.glob("lecture-cycle-*/report/summary.json")):
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        missing = sorted(REQUIRED_FIELDS - data.keys())
        if missing:
            raise SystemExit(f"현재 summary.json 스키마와 맞지 않습니다: {summary_path} / missing={missing}")
        row = {key: data[key] for key in REQUIRED_FIELDS}
        row["run"] = summary_path.parent.parent.name
        row["summary_path"] = summary_path.parent / "summary.html"
        rows.append(row)
    rows.sort(key=lambda x: (x["users"], x["run"]))
    return rows

def build(results_root: Path, output_dir: Path) -> tuple[Path, Path]:
    rows = collect(results_root)
    if not rows:
        raise SystemExit("비교할 lecture-cycle 결과가 없습니다.")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "comparison.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows([{k: row[k] for k in FIELDS} for row in rows])

    table_rows = []
    for row in rows:
        rel = os.path.relpath(row["summary_path"], start=output_dir).replace(os.sep, "/")
        cls = "pass" if row["status"] == "PASS" else "invalid" if row["status"] == "INVALID" else "fail"
        table_rows.append(
            f"<tr><td><span class='{cls}'>{html.escape(str(row['status']))}</span></td>"
            f"<td>{row['execution_complete']}</td><td>{row['users']}</td><td>{row['loops']}</td><td>{row['samples']}</td>"
            f"<td>{row['average_latency_ms']}</td><td>{row['p95_latency_ms']}</td><td>{row['p99_latency_ms']}</td>"
            f"<td>{row['average_response_ms']}</td><td>{row['throughput_rps']}</td><td>{row['error_percent']}</td>"
            f"<td><a href='{html.escape(rel)}'>{html.escape(row['run'])}</a></td></tr>"
        )
    html_path = output_dir / "comparison.html"
    html_path.write_text(f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>QA6 Part2 단계별 비교</title><style>body{{font-family:system-ui;margin:32px;background:#f7f8fa;color:#17191c}}main{{max-width:1400px;margin:auto}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:10px;border-bottom:1px solid #e7e9ed;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#eef1f4}}.pass{{color:#146b2d;font-weight:700}}.fail{{color:#a51d1d;font-weight:700}}.invalid{{color:#8a5a00;font-weight:700}}a{{color:#2457d6}}</style></head>
<body><main><h1>QA6 Part2 부하 비교</h1><p>실행별 Latency, Response Time, TPS, Error Rate를 비교합니다. 특정 단계만 재실행한 결과도 포함할 수 있습니다.</p>
<table><thead><tr><th>Status</th><th>Complete</th><th>Users</th><th>Loops</th><th>Samples</th><th>Avg Latency</th><th>P95 Latency</th><th>P99 Latency</th><th>Avg Response</th><th>TPS</th><th>Error(%)</th><th>Run</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></main></body></html>""", encoding="utf-8")
    return csv_path, html_path

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=Path("part2_performance/results"))
    parser.add_argument("--output-dir", type=Path, default=Path("part2_performance/results/comparison"))
    args = parser.parse_args()
    csv_path, html_path = build(args.results_root, args.output_dir)
    print(csv_path); print(html_path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
