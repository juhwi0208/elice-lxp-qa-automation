import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def read_test_results(result_file):
    """pytest JUnit XML에서 최종 테스트 결과를 읽는다."""
    if not result_file:
        print("PYTEST_RESULT_FILE is not set.")
        return None

    if not os.path.exists(result_file):
        print(f"Pytest result file not found: {result_file}")
        return None

    try:
        root = ET.parse(result_file).getroot()

        if root.tag == "testsuites":
            suites = root.findall("testsuite")

        elif root.tag == "testsuite":
            suites = [root]

        else:
            print(f"Unknown JUnit XML root element: {root.tag}")
            return None

        total = sum(int(suite.get("tests", 0)) for suite in suites)

        failures = sum(int(suite.get("failures", 0)) for suite in suites)

        errors = sum(int(suite.get("errors", 0)) for suite in suites)

        skipped = sum(int(suite.get("skipped", 0)) for suite in suites)

        failed = failures + errors

        passed = max(
            total - failed - skipped,
            0,
        )

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }

    except (
        ET.ParseError,
        OSError,
        ValueError,
    ) as error:
        print(f"Failed to read pytest result file: {error}")

        return None


def read_rerun_results(result_file):
    """rerun_report.py가 생성한 JSON 결과를 읽는다."""
    if not result_file:
        print("PYTEST_RERUN_RESULT_FILE is not set.")
        return None

    if not os.path.exists(result_file):
        print(f"Pytest rerun result file not found: {result_file}")
        return None

    try:
        with open(
            result_file,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return {
            "retried": int(data.get("retried", 0)),
            "recovered": int(data.get("recovered", 0)),
            "still_failed": int(data.get("still_failed", 0)),
        }

    except (
        OSError,
        ValueError,
        TypeError,
    ) as error:
        print(f"Failed to read pytest rerun result file: {error}")

        return None


def get_display_result(
    build_result,
    rerun_results,
):
    """
    Jenkins Build 상태는 변경하지 않고,
    Discord에서 flaky 복구 여부를 별도로 표현한다.
    """
    if build_result == "SUCCESS" and rerun_results and rerun_results["retried"] > 0:
        return "QA FAIL - RERUN RECOVERED"

    return build_result


def get_status_icon(
    build_result,
    rerun_results,
):
    """테스트 최종 상태에 맞는 아이콘을 반환한다."""
    if build_result == "SUCCESS" and rerun_results and rerun_results["retried"] > 0:
        return "⚠️"

    if build_result == "SUCCESS":
        return "✅"

    if build_result == "UNSTABLE":
        return "⚠️"

    if build_result == "ABORTED":
        return "⏹️"

    return "❌"


def build_message(
    test_type,
    build_result,
    job_name,
    build_number,
    results,
    rerun_results,
    allure_url,
    build_url,
):
    """Discord에 전달할 메시지를 생성한다."""
    status_icon = get_status_icon(
        build_result,
        rerun_results,
    )

    display_result = get_display_result(
        build_result,
        rerun_results,
    )

    message = (
        f"{status_icon} **TripleQ {test_type} 테스트 완료**\n\n"
        f"**결과:** {display_result}\n"
        f"**Job:** {job_name}\n"
        f"**Build:** #{build_number}\n"
    )

    if results:
        message += (
            "\n📊 **테스트 결과**\n"
            f"Total: {results['total']}\n"
            f"✅ Passed: {results['passed']}\n"
            f"❌ Failed: {results['failed']}\n"
            f"⏭️ Skipped: {results['skipped']}\n"
        )

    else:
        message += "\n📊 **테스트 결과**\n테스트 결과 파일을 확인할 수 없습니다.\n"

    if rerun_results:
        message += (
            "\n🔄 **Rerun 결과**\n"
            f"Retried: {rerun_results['retried']}\n"
            f"✅ Recovered: {rerun_results['recovered']}\n"
            f"❌ Still Failed: "
            f"{rerun_results['still_failed']}\n"
        )

    if allure_url:
        message += f"\n📊 **Allure Report**\n{allure_url}\n"

    if build_url:
        message += f"\n🔧 **Jenkins Build**\n{build_url}"

    return message


def send_discord_notification(
    webhook_url,
    message,
):
    """Discord Webhook으로 메시지를 전송한다."""
    payload = json.dumps(
        {
            "content": message,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": ("application/json; charset=utf-8"),
            "User-Agent": ("TripleQ-Jenkins/1.0"),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=10,
        ) as response:
            print(f"Discord notification sent. HTTP status: {response.status}")

    except urllib.error.HTTPError as error:
        print(f"Discord notification failed. HTTP status: {error.code}")

        body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        if body:
            print(body)

        sys.exit(1)

    except urllib.error.URLError as error:
        print(f"Discord notification failed: {error.reason}")

        sys.exit(1)


def main():
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]

    test_type = os.environ.get(
        "TEST_TYPE",
        "Automation",
    )

    build_result = os.environ.get(
        "BUILD_RESULT",
        "UNKNOWN",
    )

    job_name = os.environ.get(
        "JOB_NAME",
        "",
    )

    build_number = os.environ.get(
        "BUILD_NUMBER",
        "",
    )

    allure_url = os.environ.get(
        "ALLURE_REPORT_URL",
        "",
    )

    build_url = os.environ.get(
        "BUILD_URL",
        "",
    )

    result_file = os.environ.get(
        "PYTEST_RESULT_FILE",
        "",
    )

    rerun_result_file = os.environ.get(
        "PYTEST_RERUN_RESULT_FILE",
        "",
    )

    results = read_test_results(result_file)

    rerun_results = read_rerun_results(rerun_result_file)

    message = build_message(
        test_type=test_type,
        build_result=build_result,
        job_name=job_name,
        build_number=build_number,
        results=results,
        rerun_results=rerun_results,
        allure_url=allure_url,
        build_url=build_url,
    )

    send_discord_notification(
        webhook_url,
        message,
    )


if __name__ == "__main__":
    main()
