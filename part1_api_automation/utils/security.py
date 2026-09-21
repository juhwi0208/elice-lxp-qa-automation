"""
로그 및 오류 메시지 출력용 민감정보 마스킹 유틸리티.
사용 방법: print(mask_sensitive_data(body))
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


SENSITIVE_KEYS = {
    "authorization",
    "sessionkey",
    "access_token",
    "password",
    "cookie",
    "set-cookie",
}


def mask_sensitive_data(data: Any) -> Any:
    """
    로그/실패 메시지에 출력할 데이터에서 민감정보를 마스킹한다.

    실제 API 요청/응답 원본 객체는 변경하지 않는다.
    """
    if isinstance(data, dict):
        masked = deepcopy(data)

        for key, value in masked.items():
            if str(key).lower() in SENSITIVE_KEYS:
                masked[key] = "***"
            else:
                masked[key] = mask_sensitive_data(value)

        return masked

    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]

    if isinstance(data, tuple):
        return tuple(mask_sensitive_data(item) for item in data)

    if isinstance(data, str):
        return _mask_sensitive_text(data)

    return data


def _mask_sensitive_text(text: str) -> str:
    """JSON 문자열 또는 일반 문자열 안의 민감정보를 마스킹한다."""

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if isinstance(parsed, (dict, list)):
        return json.dumps(
            mask_sensitive_data(parsed),
            ensure_ascii=False,
        )

    masked = text

    key_pattern = r"(authorization|sessionkey|access_token|password|cookie|set-cookie)"

    masked = re.sub(
        rf'(?i)("{key_pattern}"\s*:\s*")[^"]*(")',
        r"\1***\3",
        masked,
    )

    masked = re.sub(
        rf"(?i)({key_pattern}\s*[:=]\s*)[^\s,;]+",
        r"\1***",
        masked,
    )

    masked = re.sub(
        r"(?i)([?&](?:sig|signature|x-amz-signature|x-goog-signature)=)"
        r"[^&#\s\"']+",
        r"\1***",
        masked,
    )

    return masked
