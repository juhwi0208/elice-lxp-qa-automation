"""QA6 Part2 시험 응시 시나리오를 하드 리밋 안에서만 JMeter로 실행한다."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from part2_performance.scripts.summarize_results import summarize_report

APPROVED_API_HOST = "dev-qatrack-api.dev.elicer.io"
APPROVED_ACCOUNT_HOST = "dev-qatrack-account-api.dev.elicer.io"
APPROVED_ORG = "academy"
APPROVED_COURSE_ID = 727
APPROVED_LECTURE_ID = 1581
APPROVED_WEB_TARGET = (
    "https://dev-qatrack-web.dev.elicer.io/"
    "classrooms/28f79a10-c14b-4531-9feb-53d9a5c157fc/courses/727/lectures/1581"
)
ALLOWED_USERS = {1, 5, 10, 20, 30}
LOAD_USERS = {5, 10, 20, 30}
MAX_LOOPS = 3
MIN_LOAD_RAMPUP = 90
MAX_RAMPUP = 120
MAX_PROCESS_SECONDS = 600
MIN_ACCOUNTS = 30
EXPECTED_SCENARIO_LABELS = [
    "01_GET_course_info",
    "02_POST_test_enter",
    "03_POST_test_start",
    "04_POST_test_stop",
    "05_POST_test_reset",
]


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("양의 정수여야 합니다.")
    return number


def _validate_csv(path: Path, users: int) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"계정 CSV를 찾을 수 없습니다: {resolved}")

    with resolved.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != ["login_id", "password"]:
            raise SystemExit("계정 CSV 헤더는 정확히 login_id,password 이어야 합니다.")
        rows = list(reader)

    if len(rows) < MIN_ACCOUNTS:
        raise SystemExit(
            f"계정 CSV에는 최소 {MIN_ACCOUNTS}개 계정이 필요합니다. 현재 {len(rows)}개입니다."
        )
    if len(rows) < users:
        raise SystemExit(
            f"{users}명 실행에는 최소 {users}개 계정이 필요합니다. 현재 {len(rows)}개입니다."
        )

    login_ids: list[str] = []
    for index, row in enumerate(rows, start=2):
        login_id = (row.get("login_id") or "").strip()
        password = row.get("password") or ""
        if not login_id or not password:
            raise SystemExit(f"계정 CSV {index}행의 login_id/password가 비어 있습니다.")
        login_ids.append(login_id)

    if len(set(login_ids)) != len(login_ids):
        raise SystemExit(
            "계정 CSV에 중복 login_id가 있습니다. Thread별 고유 계정을 사용할 수 없습니다."
        )
    return resolved


def _paired_child_hash_tree(parent: ET.Element, node: ET.Element) -> ET.Element | None:
    children = list(parent)
    try:
        idx = children.index(node)
    except ValueError:
        return None
    if idx + 1 < len(children) and children[idx + 1].tag == "hashTree":
        return children[idx + 1]
    return None


def _validate_jmx_structure(jmx_path: Path) -> None:
    """실전 실행 전 CSV/Loop/Timer 구조가 회귀하지 않았는지 차단한다."""
    try:
        root = ET.parse(jmx_path).getroot()
    except ET.ParseError as exc:
        raise SystemExit(f"JMX XML 파싱 실패: {exc}") from exc

    if root.find(".//CSVDataSet") is not None:
        raise SystemExit(
            "JMX 안전검사 실패: CSVDataSet이 남아 있습니다. Loop마다 계정 행을 소비할 위험이 있어 실행을 차단합니다."
        )

    account_assign = root.find(
        ".//JSR223PreProcessor[@testname='00_ACCOUNT_ASSIGN_ONCE']"
    )
    if account_assign is None:
        raise SystemExit(
            "JMX 안전검사 실패: Thread별 1회 계정 할당기(00_ACCOUNT_ASSIGN_ONCE)가 없습니다."
        )

    once = root.find(".//OnceOnlyController[@testname='Once per virtual user']")
    if once is None:
        raise SystemExit(
            "JMX 안전검사 실패: Once per virtual user 컨트롤러가 없습니다."
        )

    labels = {
        node.attrib.get("testname") for node in root.findall(".//HTTPSamplerProxy")
    }
    missing = [label for label in EXPECTED_SCENARIO_LABELS if label not in labels]
    if missing:
        raise SystemExit(f"JMX 안전검사 실패: 시나리오 단계 누락 {missing}")

    timers = root.findall(".//UniformRandomTimer")
    if len(timers) != 4:
        raise SystemExit(
            f"JMX 안전검사 실패: 동작 사이 Timer는 정확히 4개여야 합니다. 현재 {len(timers)}개입니다."
        )
    for timer in timers:
        delay = timer.find("stringProp[@name='ConstantTimer.delay']")
        random_range = timer.find("stringProp[@name='RandomTimer.range']")
        if (
            delay is None
            or delay.text != "3000"
            or random_range is None
            or random_range.text != "2000"
        ):
            raise SystemExit(
                "JMX 안전검사 실패: 모든 Timer는 3~5초(3000+random 2000)여야 합니다."
            )

    # 첫 course 요청 앞에는 Timer가 없어야 한다. Timer는 enter/start/stop/reset 직전에만 배치한다.
    for parent in root.iter("hashTree"):
        children = list(parent)
        for node in children:
            if (
                node.tag == "HTTPSamplerProxy"
                and node.attrib.get("testname") == "01_GET_course_info"
            ):
                child_ht = _paired_child_hash_tree(parent, node)
                if (
                    child_ht is not None
                    and child_ht.find("UniformRandomTimer") is not None
                ):
                    raise SystemExit(
                        "JMX 안전검사 실패: 01_GET_course_info 앞에 불필요한 Timer가 있습니다."
                    )

    # Thread/Loop 핵심 설정도 고정 검증한다.
    num_threads = root.find(
        ".//ThreadGroup/stringProp[@name='ThreadGroup.num_threads']"
    )
    loops_prop = root.find(
        ".//elementProp[@elementType='LoopController']/stringProp[@name='LoopController.loops']"
    )
    same_user = root.find(
        ".//ThreadGroup/boolProp[@name='ThreadGroup.same_user_on_next_iteration']"
    )
    scheduler = root.find(".//ThreadGroup/boolProp[@name='ThreadGroup.scheduler']")
    duration = root.find(".//ThreadGroup/longProp[@name='ThreadGroup.duration']")
    if num_threads is None or num_threads.text != "${__P(users,1)}":
        raise SystemExit(
            "JMX 안전검사 실패: Thread 수가 -Jusers 속성과 연결되어 있지 않습니다."
        )
    if loops_prop is None or loops_prop.text != "${__P(loops,1)}":
        raise SystemExit(
            "JMX 안전검사 실패: Loop 수가 -Jloops 속성과 연결되어 있지 않습니다."
        )
    if same_user is None or same_user.text != "true":
        raise SystemExit(
            "JMX 안전검사 실패: 반복 시 동일 사용자 유지 설정이 꺼져 있습니다."
        )
    if (
        scheduler is None
        or scheduler.text != "true"
        or duration is None
        or duration.text != "540"
    ):
        raise SystemExit(
            "JMX 안전검사 실패: Scheduler 540초 안전 제한이 유지되지 않았습니다."
        )

    # 시나리오 sampler는 각 1개씩만 존재해야 한다.
    sampler_names = [
        node.attrib.get("testname") for node in root.findall(".//HTTPSamplerProxy")
    ]
    for label in EXPECTED_SCENARIO_LABELS:
        if sampler_names.count(label) != 1:
            raise SystemExit(
                f"JMX 안전검사 실패: {label} sampler 개수는 정확히 1개여야 합니다."
            )

    # Timer가 enter/start/stop/reset sampler에 각각 1개씩 붙어 있는지 확인한다.
    timer_targets = set()
    for parent in root.iter("hashTree"):
        children = list(parent)
        for node in children:
            if node.tag != "HTTPSamplerProxy":
                continue
            child_ht = _paired_child_hash_tree(parent, node)
            if child_ht is not None and child_ht.find("UniformRandomTimer") is not None:
                timer_targets.add(node.attrib.get("testname"))
    expected_timer_targets = {
        "02_POST_test_enter",
        "03_POST_test_start",
        "04_POST_test_stop",
        "05_POST_test_reset",
    }
    if timer_targets != expected_timer_targets:
        raise SystemExit(
            f"JMX 안전검사 실패: Timer 대상은 {sorted(expected_timer_targets)}여야 합니다. 현재 {sorted(timer_targets)}"
        )

    # 승인된 Dev 대상이 JMX에서 변경되지 않았는지 sampler 단위로 검증한다.
    samplers = {
        node.attrib.get("testname"): node for node in root.findall(".//HTTPSamplerProxy")
    }

    def require_sampler_target(
        label: str, *, host: str, path: str, argument_name: str | None = None, argument_value: str | None = None
    ) -> None:
        sampler = samplers.get(label)
        if sampler is None:
            raise SystemExit(f"JMX 안전검사 실패: sampler 누락: {label}")
        domain = sampler.findtext("stringProp[@name='HTTPSampler.domain']")
        protocol = sampler.findtext("stringProp[@name='HTTPSampler.protocol']")
        actual_path = sampler.findtext("stringProp[@name='HTTPSampler.path']")
        if domain != host or protocol != "https" or actual_path != path:
            raise SystemExit(
                f"JMX 안전검사 실패: {label} 대상이 승인된 Dev 대상과 다릅니다. "
                f"host={domain}, protocol={protocol}, path={actual_path}"
            )
        if argument_name is not None:
            values = {}
            for prop in sampler.findall(".//elementProp[@elementType='HTTPArgument']"):
                name = prop.findtext("stringProp[@name='Argument.name']")
                value = prop.findtext("stringProp[@name='Argument.value']")
                if name:
                    values[name] = value
            if values.get(argument_name) != argument_value:
                raise SystemExit(
                    f"JMX 안전검사 실패: {label}의 {argument_name}가 승인 값 {argument_value}와 다릅니다. "
                    f"현재 {values.get(argument_name)}"
                )

    require_sampler_target(
        "00_AUTH_login", host=APPROVED_ACCOUNT_HOST, path="/login/pw"
    )
    require_sampler_target(
        "01_GET_course_info", host=APPROVED_API_HOST,
        path=f"/org/{APPROVED_ORG}/course/get/",
        argument_name="course_id", argument_value=str(APPROVED_COURSE_ID),
    )
    for label, path in [
        ("02_POST_test_enter", f"/org/{APPROVED_ORG}/user/lecture/test/enter/"),
        ("03_POST_test_start", f"/org/{APPROVED_ORG}/user/lecture/test/start/"),
        ("04_POST_test_stop", f"/org/{APPROVED_ORG}/user/lecture/test/stop/"),
        ("05_POST_test_reset", f"/org/{APPROVED_ORG}/lecture/test/reset/by_self/"),
    ]:
        require_sampler_target(
            label, host=APPROVED_API_HOST, path=path,
            argument_name="lecture_id", argument_value=str(APPROVED_LECTURE_ID),
        )

    text = jmx_path.read_text(encoding="utf-8")
    for expected in [
        "/org/academy/course/get/",
        "/org/academy/user/lecture/test/enter/",
        "/org/academy/user/lecture/test/start/",
        "/org/academy/user/lecture/test/stop/",
        "/org/academy/lecture/test/reset/by_self/",
        '<stringProp name="ThreadGroup.on_sample_error">stoptestnow</stringProp>',
    ]:
        if expected not in text:
            raise SystemExit(f"JMX 안전검사 실패: 필수 설정 누락: {expected}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--users", type=_positive_int, required=True, choices=sorted(ALLOWED_USERS)
    )
    parser.add_argument("--loops", type=_positive_int, default=1)
    parser.add_argument("--rampup", type=_positive_int)
    parser.add_argument("--accounts-csv", type=Path, required=True)
    parser.add_argument("--jmeter", default=os.getenv("JMETER_BIN", "jmeter"))
    parser.add_argument(
        "--results-root", type=Path, default=Path("part2_performance/results")
    )
    parser.add_argument(
        "--confirm-approved-window",
        action="store_true",
        help="코치진과 합의된 Dev 저부하 실행 시간임을 명시합니다.",
    )
    return parser


def _validate_limits(args: argparse.Namespace) -> int:
    if not args.confirm_approved_window:
        raise SystemExit(
            "--confirm-approved-window 옵션이 필요합니다. 합의된 시간 외에는 실행하지 마세요."
        )
    if args.loops > MAX_LOOPS:
        raise SystemExit(f"Loop는 하드 리밋 {MAX_LOOPS}회를 초과할 수 없습니다.")

    if args.rampup is None:
        rampup = 1 if args.users == 1 else MIN_LOAD_RAMPUP
    else:
        rampup = args.rampup

    if args.users in LOAD_USERS and not (MIN_LOAD_RAMPUP <= rampup <= MAX_RAMPUP):
        raise SystemExit(
            f"5명 이상 단계 Ramp-up은 {MIN_LOAD_RAMPUP}~{MAX_RAMPUP}초여야 합니다."
        )
    if args.users == 1 and not (1 <= rampup <= MAX_RAMPUP):
        raise SystemExit(f"1-user smoke Ramp-up은 1~{MAX_RAMPUP}초 범위여야 합니다.")
    return rampup


def _resolve_java_env() -> dict[str, str]:
    child_env = os.environ.copy()
    child_env.pop("JMETER_BIN", None)
    candidates = [
        Path(r"C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"),
        Path(r"C:\Users\Bell\.jdks\corretto-17.0.14"),
    ]
    for candidate in candidates:
        if (candidate / "bin" / "java.exe").is_file():
            child_env["JAVA_HOME"] = str(candidate)
            child_env["PATH"] = f"{candidate / 'bin'};{child_env.get('PATH', '')}"
            break
    return child_env


def main() -> int:
    args = _build_parser().parse_args()
    rampup = _validate_limits(args)
    accounts_csv = _validate_csv(args.accounts_csv, args.users)

    jmeter_bin = shutil.which(args.jmeter)
    if not jmeter_bin:
        raise SystemExit(f"JMeter 실행 파일을 찾을 수 없습니다: {args.jmeter}")

    jmx_path = Path("part2_performance/jmeter/lecture_test_cycle.jmx").resolve()
    if not jmx_path.is_file():
        raise SystemExit(f"JMX 파일이 없습니다: {jmx_path}")
    _validate_jmx_structure(jmx_path)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = (
        args.results_root / f"lecture-cycle-{args.users}u-{args.loops}loop-{timestamp}"
    )
    report_dir = run_dir / "report"
    run_dir.mkdir(parents=True, exist_ok=False)
    jtl_path = run_dir / "samples.jtl"
    log_path = run_dir / "jmeter.log"

    command = [
        jmeter_bin,
        "-n",
        "-t",
        str(jmx_path),
        f"-Jusers={args.users}",
        f"-Jrampup={rampup}",
        f"-Jloops={args.loops}",
        f"-JaccountsCsv={accounts_csv}",
        "-l",
        str(jtl_path),
        "-j",
        str(log_path),
        "-e",
        "-o",
        str(report_dir),
    ]

    print("[QA6 Part2 APPROVED LOW-LOAD]")
    print(f"Target : {APPROVED_WEB_TARGET}")
    print(f"API    : https://{APPROVED_API_HOST}/org/{APPROVED_ORG}/...")
    print(f"Course : {APPROVED_COURSE_ID}, Lecture: {APPROVED_LECTURE_ID}")
    print(f"Users  : {args.users}, Ramp-up: {rampup}s, Loops: {args.loops}")
    print(
        f"Expect : each scenario API {args.users * args.loops} samples / {args.users} unique threads"
    )
    print("Account: CSV row is assigned ONCE per thread and reused for all loops")
    print("Pacing : 4 inter-action Uniform Random Timers, each 3~5s")
    print("Kill   : any sample failure stops test; HTTP 5xx triggers stopTestNow")
    print("Judge  : incomplete users×loops execution => INVALID (never PASS)")

    try:
        completed = subprocess.run(
            command,
            check=False,
            timeout=MAX_PROCESS_SECONDS,
            env=_resolve_java_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(
            "단일 실행 안전 상한 600초에 도달하여 JMeter 프로세스를 강제 종료했습니다."
        ) from exc

    if not report_dir.is_dir():
        log_hint = f" 로그 확인: {log_path}" if log_path.exists() else ""
        raise SystemExit(f"JMeter HTML Dashboard가 생성되지 않았습니다.{log_hint}")

    summary = summarize_report(report_dir, args.users, args.loops, run_dir=run_dir)
    print(
        "Result : "
        f"status={summary['status']}, complete={summary['execution_complete']}, "
        f"avg_latency={summary['average_latency_ms']}ms, p95_latency={summary['p95_latency_ms']}ms, "
        f"throughput={summary['throughput_rps']}req/s, error={summary['error_percent']}%"
    )
    if summary["integrity_errors"]:
        for message in summary["integrity_errors"]:
            print(f"INVALID: {message}")
    print(f"Report : {report_dir / 'summary.html'}")

    if completed.returncode != 0:
        raise SystemExit(
            f"JMeter가 비정상 종료되었습니다(return code={completed.returncode}). {log_path}"
        )
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
