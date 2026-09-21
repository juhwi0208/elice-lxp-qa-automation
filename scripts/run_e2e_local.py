"""로컬 E2E 테스트 실행 및 HTML 리포트 자동 생성 스크립트.

기능:
1. 내일/다음주 일정 기준 환경변수 동적 계산 및 주입
2. pytest 실행 (Headed/Headless, pytest-html, allure, junitxml)
3. Allure 단일 파일(single-file) HTML 리포트 자동 생성
4. 결과 HTML 파일 경로 출력
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent


def setup_schedule_dates() -> None:
    """내일 및 다음 주 일정을 기준으로 환경변수를 설정한다."""
    try:
        tz = ZoneInfo("Asia/Seoul")
    except Exception:
        tz = None

    now = datetime.now(tz) if tz else datetime.now()
    tomorrow = now + timedelta(days=1)
    seven_days_later = now + timedelta(days=7)

    start_dt = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    end_dt = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
    all_day_dt = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    recurring_dt = seven_days_later.replace(hour=23, minute=59, second=59, microsecond=0)

    # ISO 8601 형식 (+09:00 포함)
    tz_suffix = "+09:00"
    os.environ["LXP_E2E_SCHEDULE_START"] = start_dt.strftime("%Y-%m-%dT%H:%M:%S") + tz_suffix
    os.environ["LXP_E2E_SCHEDULE_END"] = end_dt.strftime("%Y-%m-%dT%H:%M:%S") + tz_suffix
    os.environ["LXP_E2E_ALL_DAY_DATE"] = all_day_dt.strftime("%Y-%m-%dT%H:%M:%S") + tz_suffix
    os.environ["LXP_E2E_RECURRING_UNTIL"] = recurring_dt.strftime("%Y-%m-%dT%H:%M:%S") + tz_suffix

    print(f"[설정] 일정 시작: {os.environ['LXP_E2E_SCHEDULE_START']}")
    print(f"[설정] 일정 종료: {os.environ['LXP_E2E_SCHEDULE_END']}")
    print(f"[설정] 종일 일정: {os.environ['LXP_E2E_ALL_DAY_DATE']}")
    print(f"[설정] 반복 종료: {os.environ['LXP_E2E_RECURRING_UNTIL']}")


def prepare_directories() -> None:
    """테스트 결과 및 아티팩트 디렉토리를 정리한다."""
    (ROOT_DIR / "pytest-results").mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "allure-results" / "e2e").mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "allure-report" / "e2e").mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "artifacts" / "tc-results").mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "artifacts" / "screenshots").mkdir(parents=True, exist_ok=True)

    # 이전 tc_results.jsonl 제거
    tc_result_file = ROOT_DIR / "artifacts" / "tc-results" / "tc_results.jsonl"
    if tc_result_file.exists():
        try:
            tc_result_file.unlink()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="로컬 E2E 테스트 실행 및 HTML 생성")
    parser.add_argument(
        "--target",
        default="part3_e2e/tests/e2e_integration",
        help="실행할 테스트 경로 또는 모듈 (기본: part3_e2e/tests/e2e_integration)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        default=False,
        help="브라우저 창을 화면에 표시 (기본값: headless)",
    )
    parser.add_argument(
        "-k",
        dest="keyword",
        default="",
        help="pytest -k 키워드 필터 (예: independent, flow 등)",
    )
    parser.add_argument(
        "--reruns",
        type=int,
        default=0,
        help="실패 시 재시도 횟수 (기본값: 0)",
    )
    parser.add_argument(
        "--html-report",
        default="pytest-results/e2e-report.html",
        help="생성할 pytest HTML 리포트 경로",
    )
    parser.add_argument(
        "--allure-single-file",
        action="store_true",
        default=True,
        help="Allure 리포트를 단일 HTML 파일로 생성",
    )

    args = parser.parse_args()

    # .env 로드
    load_dotenv(ROOT_DIR / ".env")

    # 기본 환경변수 보정
    setup_schedule_dates()
    prepare_directories()

    python_exe = sys.executable

    # pytest 커맨드 구성
    cmd = [
        python_exe,
        "-m",
        "pytest",
        args.target,
        "-v",
        f"--html={args.html_report}",
        "--self-contained-html",
        "--alluredir=allure-results/e2e",
        "--clean-alluredir",
        "--junitxml=pytest-results/e2e.xml",
    ]

    if args.headed:
        cmd.append("--selenium-headed")

    if args.keyword:
        cmd.extend(["-k", args.keyword])

    if args.reruns > 0:
        cmd.extend(["--reruns", str(args.reruns), "--reruns-delay", "2"])

    print("\n" + "=" * 60)
    print(f"[실행] E2E 테스트 시작: {' '.join(cmd)}")
    print(f"[모드] 브라우저: {'Headed (창 표시)' if args.headed else 'Headless (백그라운드)'}")
    print(f"[대상] {args.target}")
    print("=" * 60 + "\n")

    pytest_exit_code = subprocess.run(cmd, cwd=str(ROOT_DIR)).returncode

    print("\n" + "=" * 60)
    print(f"[완료] Pytest 실행 종료 (Exit Code: {pytest_exit_code})")
    print("=" * 60 + "\n")

    # Allure 단일 파일 리포트 생성
    allure_html_path = ROOT_DIR / "allure-report" / "e2e" / "index.html"
    allure_bin = shutil.which("allure")
    if not allure_bin:
        # AppData Roaming 경로 확인
        appdata_allure = Path(os.environ.get("APPDATA", "")) / "npm" / "allure.cmd"
        if appdata_allure.exists():
            allure_bin = str(appdata_allure)

    if allure_bin:
        print("[리포트] Allure 단일 HTML 리포트 생성 중...")
        allure_cmd = [
            allure_bin,
            "generate",
            "allure-results/e2e",
            "-o",
            "allure-report/e2e",
            "--clean",
        ]
        if args.allure_single_file:
            allure_cmd.append("--single-file")

        subprocess.run(allure_cmd, cwd=str(ROOT_DIR), shell=True)
    else:
        print("[경고] allure CLI를 찾을 수 없어 Allure 리포트 생성을 건너뜁니다.")

    # 생성된 HTML 리포트 경로 안내
    pytest_html = ROOT_DIR / args.html_report
    print("\n" + "=" * 60)
    print("  생성된 HTML 리포트 목록:")
    if pytest_html.exists():
        print(f"  1. Pytest HTML 리포트: file:///{pytest_html.resolve().as_posix()}")
    if allure_html_path.exists():
        print(f"  2. Allure HTML 리포트: file:///{allure_html_path.resolve().as_posix()}")
    print("=" * 60 + "\n")

    return pytest_exit_code


if __name__ == "__main__":
    sys.exit(main())
