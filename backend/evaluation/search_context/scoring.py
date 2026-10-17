import re
from typing import Any

from .cases import SearchContextCase


def screen_plan(case: SearchContextCase, plan: dict[str, Any]) -> dict[str, Any]:
    query = str(plan.get("en_query", ""))
    checks: dict[str, bool] = {
        f"topic:{pattern}": bool(re.search(pattern, query, re.IGNORECASE))
        for pattern in case.topic_patterns
    }
    checks.update({
        f"forbidden:{pattern}": not bool(re.search(pattern, query, re.IGNORECASE))
        for pattern in case.forbidden_patterns
    })
    for key, expected in case.expected_fields.items():
        actual = plan.get(key)
        if isinstance(expected, list):
            checks[f"field:{key}"] = (
                isinstance(actual, list)
                and len(actual) == len(expected)
                and all(isinstance(value, str) for value in actual)
                and all(isinstance(value, str) for value in expected)
                and sorted(actual) == sorted(expected)
            )
        else:
            checks[f"field:{key}"] = actual == expected
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "failed_checks": [key for key, passed in checks.items() if not passed],
        "diagnostic_only": case.diagnostic_only,
    }


def prompt_contains_topic(case: SearchContextCase, prompt: str) -> bool | None:
    if not case.topic_patterns:
        return None
    return all(re.search(pattern, prompt, re.IGNORECASE) for pattern in case.topic_patterns)
