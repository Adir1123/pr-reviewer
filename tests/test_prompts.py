from reviewer.prompts import SYSTEM_PROMPT, build_user_prompt


def test_system_prompt_contains_code_review_checklist():
    assert "Naming clarity" in SYSTEM_PROMPT
    assert "Dead code" in SYSTEM_PROMPT
    assert "Error handling at system boundaries" in SYSTEM_PROMPT
    assert "Separation of concerns" in SYSTEM_PROMPT


def test_system_prompt_contains_security_checklist():
    assert "SQL" in SYSTEM_PROMPT
    assert "Hardcoded secrets" in SYSTEM_PROMPT
    assert "Auth/permission" in SYSTEM_PROMPT
    assert "Sensitive data in logs" in SYSTEM_PROMPT


def test_system_prompt_enforces_section_format():
    assert "### Bugs" in SYSTEM_PROMPT
    assert "### Security" in SYSTEM_PROMPT
    assert "### Code Quality" in SYSTEM_PROMPT
    assert "### Suggestions" in SYSTEM_PROMPT


def test_build_user_prompt_includes_all_context():
    result = build_user_prompt(
        pr_title="Fix auth bug",
        pr_body="Fixes the login issue",
        file_list=["auth.py", "tests/test_auth.py"],
        diff="--- a/auth.py\n+++ b/auth.py\n@@ -1 +1 @@\n-x\n+y",
    )
    assert "Fix auth bug" in result
    assert "Fixes the login issue" in result
    assert "auth.py" in result
    assert "--- a/auth.py" in result


def test_build_user_prompt_handles_none_body():
    result = build_user_prompt("title", None, [], "diff")
    assert "No description provided." in result


def test_build_user_prompt_handles_empty_body():
    result = build_user_prompt("title", "", [], "diff")
    assert "No description provided." in result


def test_build_user_prompt_handles_empty_file_list():
    result = build_user_prompt("title", "body", [], "diff")
    assert "No files listed." in result
