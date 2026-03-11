import re
import logging

SECTION_PATTERN = re.compile(r"^### (Bugs|Security|Code Quality|Suggestions)")
SECTION_KEYS = {
    "Bugs": "bugs",
    "Security": "security",
    "Code Quality": "code_quality",
    "Suggestions": "suggestions",
}


def format_review(raw: str) -> dict:
    """Parse Claude's raw response into a dict with four section lists."""
    result: dict[str, list[str]] = {key: [] for key in SECTION_KEYS.values()}
    current_section = None

    for line in raw.splitlines():
        match = SECTION_PATTERN.match(line)
        if match:
            current_section = SECTION_KEYS[match.group(1)]
            continue
        if current_section is None:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            result[current_section].append(stripped[2:])
        elif stripped and not stripped.startswith("#"):
            result[current_section].append(stripped)

    if not any(result.values()):
        logging.warning("formatter: no sections found in Claude response")
        return {key: ["No issues found."] for key in SECTION_KEYS.values()}

    for key in result:
        if not result[key]:
            result[key] = ["No issues found."]

    return result
