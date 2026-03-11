from reviewer.formatter import format_review

VALID_RESPONSE = """\
### Bugs
- Off-by-one error on line 42
- Null pointer on line 87

### Security
- SQL injection on line 31

### Code Quality
- Function too long

### Suggestions
- Add type hints
"""


def test_parses_all_four_sections():
    result = format_review(VALID_RESPONSE)
    assert "Off-by-one error on line 42" in result["bugs"]
    assert "Null pointer on line 87" in result["bugs"]
    assert "SQL injection on line 31" in result["security"]
    assert "Function too long" in result["code_quality"]
    assert "Add type hints" in result["suggestions"]


def test_discards_preamble_before_first_heading():
    raw = "Here is my review:\n\n### Bugs\n- Bug 1\n\n### Security\n- No issues found.\n\n### Code Quality\n- Issue\n\n### Suggestions\n- Tip"
    result = format_review(raw)
    assert result["bugs"] == ["Bug 1"]
    assert "Here is my review" not in str(result)


def test_missing_section_defaults_to_no_issues():
    raw = "### Bugs\n- Bug 1\n\n### Security\n- Vuln\n\n### Code Quality\n- Issue"
    result = format_review(raw)
    assert result["suggestions"] == ["No issues found."]


def test_empty_section_defaults_to_no_issues():
    raw = "### Bugs\n\n### Security\n- Vuln\n\n### Code Quality\n- Issue\n\n### Suggestions\n"
    result = format_review(raw)
    assert result["bugs"] == ["No issues found."]


def test_fully_malformed_returns_all_defaults():
    result = format_review("This is not a valid review at all.")
    assert result["bugs"] == ["No issues found."]
    assert result["security"] == ["No issues found."]
    assert result["code_quality"] == ["No issues found."]
    assert result["suggestions"] == ["No issues found."]


def test_handles_leading_spaces_on_bullet_points():
    raw = "### Bugs\n  - Bug with leading spaces\n\n### Security\n- No issues found.\n\n### Code Quality\n- No issues found.\n\n### Suggestions\n- No issues found."
    result = format_review(raw)
    assert "Bug with leading spaces" in result["bugs"]


def test_returns_dict_with_correct_keys():
    result = format_review(VALID_RESPONSE)
    assert set(result.keys()) == {"bugs", "security", "code_quality", "suggestions"}
