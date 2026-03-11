# GitHub PR AI Reviewer — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable GitHub Actions workflow + Python package that automatically posts structured AI code reviews on pull requests using Claude Opus.

**Architecture:** A composite GitHub Action triggers a Python package (`reviewer/`) on every `pull_request` event. `main.py` orchestrates four modules: `fetcher.py` gets the PR diff from GitHub, `main.py` truncates if needed, `analyzer.py` calls Claude Opus, `formatter.py` parses the response into 4 sections, and `poster.py` posts or updates the review comment.

**Tech Stack:** Python 3.12, `anthropic` SDK (`claude-opus-4-6`), `PyGithub`, `pytest` + `pytest-mock`, `python-dotenv`, GitHub Actions (reusable workflow + composite action).

---

## File Structure

| File | Responsibility |
|---|---|
| `reviewer/__init__.py` | Package marker (empty) |
| `reviewer/prompts.py` | `SYSTEM_PROMPT` + `build_user_prompt()` |
| `reviewer/fetcher.py` | `fetch_pr_data()` — GitHub API → PR dict |
| `reviewer/analyzer.py` | `analyze()` — PR dict → raw Claude string, with retry |
| `reviewer/formatter.py` | `format_review()` — raw string → structured dict |
| `reviewer/poster.py` | `post_review()`, `_build_comment()`, `_find_existing_comment()` |
| `reviewer/main.py` | Entry point — env validation, truncation, orchestration, error handling |
| `tests/__init__.py` | Package marker (empty) |
| `tests/test_prompts.py` | Tests for prompt content and `build_user_prompt()` |
| `tests/test_fetcher.py` | Tests for `fetch_pr_data()` with mocked PyGithub |
| `tests/test_analyzer.py` | Tests for `analyze()` with mocked Anthropic SDK |
| `tests/test_formatter.py` | Pure parsing tests for `format_review()` |
| `tests/test_poster.py` | Tests for comment assembly and posting logic |
| `tests/test_main.py` | Tests for orchestration, truncation, and error paths |
| `action.yml` | Composite action definition |
| `.github/workflows/review.yml` | Reusable workflow for target repos |
| `.github/workflows/test.yml` | CI: runs pytest on push/PR |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for local dev env vars |
| `.gitignore` | Ignores `.env`, caches, dist |
| `README.md` | Docs with Mermaid diagram and quick start |

**Spec:** `docs/superpowers/specs/2026-03-11-github-pr-reviewer-design.md`

---

## Chunk 1: Scaffold + Prompts

### Task 1: Initialize project structure

**Files:**
- Create: `reviewer/__init__.py`
- Create: `tests/__init__.py`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create directories**

```bash
mkdir -p reviewer tests .github/workflows
```

- [ ] **Step 2: Create `requirements.txt`**

```
anthropic>=0.40.0
PyGithub>=2.3.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 3: Create `.env.example`**

```
ANTHROPIC_API_KEY=your_key_here
GITHUB_TOKEN=your_personal_access_token
PR_NUMBER=1
REPO=owner/repo
PR_SHA=abc1234
```

- [ ] **Step 4: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.coverage
dist/
*.egg-info/
```

- [ ] **Step 5: Create empty package markers**

```bash
touch reviewer/__init__.py tests/__init__.py
```

- [ ] **Step 6: Install dependencies**

```bash
pip install --upgrade pip && pip install -r requirements.txt
```

Expected: All packages install without errors.

- [ ] **Step 7: Verify pytest runs (no tests yet)**

```bash
pytest -v
```

Expected: `no tests ran` — no errors.

- [ ] **Step 8: Commit**

```bash
git add reviewer/__init__.py tests/__init__.py requirements.txt .env.example .gitignore
# Note: if touch created tests/__init__.py as untracked, git add . covers it
git commit -m "feat: initialize project structure"
```

---

### Task 2: prompts.py — system prompt and user prompt builder

**Files:**
- Create: `reviewer/prompts.py`
- Create: `tests/test_prompts.py`
- Test: `tests/test_prompts.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_prompts.py`:

```python
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
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_prompts.py -v
```

Expected: `ModuleNotFoundError` — `prompts` does not exist yet.

- [ ] **Step 3: Create `reviewer/prompts.py`**

```python
SYSTEM_PROMPT = """You are a senior software engineer performing a code review.

Review the provided diff carefully using these checklists:

Code Review Checklist:
- Naming clarity, function length, complexity
- Dead code, unused imports
- Error handling at system boundaries
- Test coverage of new logic
- Separation of concerns

Security Checklist (OWASP Top 10):
- SQL/command injection via string interpolation
- Hardcoded secrets or API keys
- Insecure deserialization
- Missing input validation at system boundaries
- Auth/permission checks
- Sensitive data in logs

Respond in exactly this format using ### headings:

### Bugs
- <findings or "No issues found.">

### Security
- <findings or "No issues found.">

### Code Quality
- <findings or "No issues found.">

### Suggestions
- <findings or "No issues found.">

Use bullet points under each heading. If no issues in a section, write exactly \
"No issues found." Be specific and cite line numbers when possible. Be concise."""


def build_user_prompt(
    pr_title: str,
    pr_body: str,
    file_list: list[str],
    diff: str,
) -> str:
    """Build the user prompt with PR context injected."""
    body = pr_body if pr_body else "No description provided."
    files = "\n".join(file_list) if file_list else "No files listed."
    return f"""PR Title: {pr_title}

PR Description: {body}

Changed files:
{files}

Diff:
{diff}"""
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_prompts.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add reviewer/prompts.py tests/test_prompts.py
git commit -m "feat: add prompts with code review and security checklists"
```

---

## Chunk 2: Fetcher + Analyzer

### Task 3: fetcher.py — fetch PR diff from GitHub

**Files:**
- Create: `reviewer/fetcher.py`
- Create: `tests/test_fetcher.py`
- Test: `tests/test_fetcher.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_fetcher.py`:

```python
from unittest.mock import MagicMock, patch
from reviewer.fetcher import fetch_pr_data


def _make_file(filename, patch_text=None):
    f = MagicMock()
    f.filename = filename
    f.patch = patch_text
    return f


def _make_pull(title, body, files):
    pull = MagicMock()
    pull.title = title
    pull.body = body
    pull.get_files.return_value = files
    return pull


@patch("reviewer.fetcher.Github")
def test_returns_correct_keys(mock_github):
    file1 = _make_file("main.py", "@@ -1 +1 @@\n-x\n+y")
    pull = _make_pull("Fix bug", "Some description", [file1])
    mock_github.return_value.get_repo.return_value.get_pull.return_value = pull

    result = fetch_pr_data("owner/repo", 1, "token")

    assert result["title"] == "Fix bug"
    assert result["body"] == "Some description"
    assert result["files"] == ["main.py"]
    assert "main.py" in result["diff"]


@patch("reviewer.fetcher.Github")
def test_body_is_empty_string_when_none(mock_github):
    pull = _make_pull("Fix bug", None, [_make_file("main.py", "@@\n-x\n+y")])
    mock_github.return_value.get_repo.return_value.get_pull.return_value = pull

    result = fetch_pr_data("owner/repo", 1, "token")

    assert result["body"] == ""


@patch("reviewer.fetcher.Github")
def test_diff_excludes_files_without_patch(mock_github):
    file1 = _make_file("main.py", "@@ -1 +1 @@\n-x\n+y")
    file2 = _make_file("binary.bin", None)
    pull = _make_pull("Fix bug", "body", [file1, file2])
    mock_github.return_value.get_repo.return_value.get_pull.return_value = pull

    result = fetch_pr_data("owner/repo", 1, "token")

    assert "binary.bin" in result["files"]
    assert "binary.bin" not in result["diff"]


@patch("reviewer.fetcher.Github")
def test_diff_format_includes_file_headers(mock_github):
    file1 = _make_file("auth.py", "@@ -10,7 +10,7 @@\n-old\n+new")
    pull = _make_pull("title", "body", [file1])
    mock_github.return_value.get_repo.return_value.get_pull.return_value = pull

    result = fetch_pr_data("owner/repo", 1, "token")

    assert "--- a/auth.py" in result["diff"]
    assert "+++ b/auth.py" in result["diff"]
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_fetcher.py -v
```

Expected: `ModuleNotFoundError` — `fetcher` does not exist yet.

- [ ] **Step 3: Create `reviewer/fetcher.py`**

```python
from github import Github


def fetch_pr_data(repo: str, pr_number: int, token: str) -> dict:
    """Fetch PR metadata and unified diff from GitHub."""
    g = Github(token)
    pull = g.get_repo(repo).get_pull(pr_number)
    pr_files = list(pull.get_files())  # single API call, reused below
    files = [f.filename for f in pr_files]
    diff = _build_diff(pr_files)
    return {
        "title": pull.title,
        "body": pull.body or "",
        "files": files,
        "diff": diff,
    }


def _build_diff(pr_files: list) -> str:
    """Build a unified diff string from all PR file patches."""
    parts = []
    for f in pr_files:
        if f.patch:
            parts.append(f"--- a/{f.filename}\n+++ b/{f.filename}\n{f.patch}")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_fetcher.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add reviewer/fetcher.py tests/test_fetcher.py
git commit -m "feat: add fetcher to retrieve PR diff from GitHub API"
```

---

### Task 4: analyzer.py — call Claude Opus with retry logic

**Files:**
- Create: `reviewer/analyzer.py`
- Create: `tests/test_analyzer.py`
- Test: `tests/test_analyzer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_analyzer.py`:

```python
import anthropic
import httpx
import pytest
from unittest.mock import MagicMock, patch
from reviewer.analyzer import analyze

PR_DATA = {
    "title": "Fix auth bug",
    "body": "Fixes login",
    "files": ["auth.py"],
    "diff": "--- a/auth.py\n+++ b/auth.py\n@@ -1 +1 @@\n-x\n+y",
}


def _make_response(text="### Bugs\n- No issues found."):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def _make_rate_limit_error(retry_after="30"):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, request=request, headers={"retry-after": retry_after})
    return anthropic.RateLimitError("Rate limit exceeded", response=response, body=None)


def _make_api_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(500, request=request)
    return anthropic.InternalServerError("Server error", response=response, body=None)


@patch("reviewer.analyzer.anthropic.Anthropic")
def test_analyze_returns_raw_text(mock_client_class):
    mock_client_class.return_value.messages.create.return_value = _make_response("review text")
    result = analyze(PR_DATA, "key")
    assert result == "review text"


@patch("reviewer.analyzer.anthropic.Anthropic")
def test_analyze_uses_correct_model(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_client.messages.create.return_value = _make_response()
    analyze(PR_DATA, "key")
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-6"


@patch("reviewer.analyzer.time.sleep")
@patch("reviewer.analyzer.anthropic.Anthropic")
def test_retries_on_rate_limit_using_header(mock_client_class, mock_sleep):
    mock_client = mock_client_class.return_value
    mock_client.messages.create.side_effect = [
        _make_rate_limit_error("30"),
        _make_response(),
    ]
    analyze(PR_DATA, "key")
    mock_sleep.assert_called_once_with(30)
    assert mock_client.messages.create.call_count == 2


@patch("reviewer.analyzer.time.sleep")
@patch("reviewer.analyzer.anthropic.Anthropic")
def test_rate_limit_falls_back_to_60s_on_invalid_header(mock_client_class, mock_sleep):
    mock_client = mock_client_class.return_value
    mock_client.messages.create.side_effect = [
        _make_rate_limit_error("Wed, 11 Mar 2026 12:00:00 GMT"),
        _make_response(),
    ]
    analyze(PR_DATA, "key")
    mock_sleep.assert_called_once_with(60)


@patch("reviewer.analyzer.time.sleep")
@patch("reviewer.analyzer.anthropic.Anthropic")
def test_retries_on_api_error_after_2s(mock_client_class, mock_sleep):
    mock_client = mock_client_class.return_value
    mock_client.messages.create.side_effect = [_make_api_error(), _make_response()]
    analyze(PR_DATA, "key")
    mock_sleep.assert_called_once_with(2)
    assert mock_client.messages.create.call_count == 2


@patch("reviewer.analyzer.time.sleep")
@patch("reviewer.analyzer.anthropic.Anthropic")
def test_raises_after_retry_exhausted(mock_client_class, mock_sleep):
    mock_client = mock_client_class.return_value
    error = _make_api_error()
    mock_client.messages.create.side_effect = [error, error]
    with pytest.raises(anthropic.APIError):
        analyze(PR_DATA, "key")
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_analyzer.py -v
```

Expected: `ModuleNotFoundError` — `analyzer` does not exist yet.

- [ ] **Step 3: Create `reviewer/analyzer.py`**

```python
import time
import anthropic
from reviewer.prompts import SYSTEM_PROMPT, build_user_prompt


def analyze(pr_data: dict, api_key: str) -> str:
    """Send PR diff to Claude Opus and return raw review text."""
    client = anthropic.Anthropic(api_key=api_key)
    return _call_with_retry(client, pr_data)


def _call_with_retry(client: anthropic.Anthropic, pr_data: dict) -> str:
    """Call Claude API with one retry on failure."""
    user_prompt = build_user_prompt(
        pr_title=pr_data["title"],
        pr_body=pr_data["body"],
        file_list=pr_data["files"],
        diff=pr_data["diff"],
    )

    def _call() -> str:
        return client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        ).content[0].text

    try:
        return _call()
    except anthropic.RateLimitError as e:
        try:
            wait = int(float(e.response.headers.get("retry-after", 60)))
        except (ValueError, TypeError):
            wait = 60
        time.sleep(wait)
        return _call()
    except anthropic.APIError:
        time.sleep(2)
        return _call()
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_analyzer.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add reviewer/analyzer.py tests/test_analyzer.py
git commit -m "feat: add analyzer with Claude Opus integration and retry logic"
```

---

## Chunk 3: Formatter + Poster

### Task 5: formatter.py — parse Claude's response into sections

**Files:**
- Create: `reviewer/formatter.py`
- Create: `tests/test_formatter.py`
- Test: `tests/test_formatter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_formatter.py`:

```python
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
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_formatter.py -v
```

Expected: `ModuleNotFoundError` — `formatter` does not exist yet.

- [ ] **Step 3: Create `reviewer/formatter.py`**

```python
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
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_formatter.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add reviewer/formatter.py tests/test_formatter.py
git commit -m "feat: add formatter to parse Claude response into structured sections"
```

---

### Task 6: poster.py — post or update PR review comment

**Files:**
- Create: `reviewer/poster.py`
- Create: `tests/test_poster.py`
- Test: `tests/test_poster.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_poster.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from github import GithubException
from reviewer.poster import post_review, _build_comment, _find_existing_comment

REVIEW = {
    "bugs": ["Off-by-one on line 42"],
    "security": ["No issues found."],
    "code_quality": ["Function too long"],
    "suggestions": ["Add type hints"],
}


def test_build_comment_contains_all_sections():
    body = _build_comment(REVIEW, "abc1234", truncated=False)
    assert "## AI Code Review" in body
    assert "**Model:** claude-opus-4-6" in body
    assert "**Commit:** abc1234" in body
    assert "### Bugs" in body
    assert "- Off-by-one on line 42" in body
    assert "### Security" in body
    assert "### Code Quality" in body
    assert "### Suggestions" in body


def test_build_comment_body_starts_with_marker():
    body = _build_comment(REVIEW, "abc1234", truncated=False)
    assert body.startswith("## AI Code Review")


def test_build_comment_includes_truncation_notice():
    body = _build_comment(REVIEW, "abc1234", truncated=True)
    assert "> Diff truncated" in body


def test_build_comment_no_truncation_notice_when_false():
    body = _build_comment(REVIEW, "abc1234", truncated=False)
    assert "Diff truncated" not in body


def test_find_existing_comment_matches_ai_review():
    comment = MagicMock()
    comment.body = "## AI Code Review\n\n**Model:** claude-opus-4-6"
    pull = MagicMock()
    pull.get_issue_comments.return_value = [comment]
    assert _find_existing_comment(pull) is comment


def test_find_existing_comment_returns_none_when_no_match():
    comment = MagicMock()
    comment.body = "Just a regular comment"
    pull = MagicMock()
    pull.get_issue_comments.return_value = [comment]
    assert _find_existing_comment(pull) is None


def test_find_existing_comment_handles_leading_whitespace():
    comment = MagicMock()
    comment.body = "  \n## AI Code Review\n\nsome content"
    pull = MagicMock()
    pull.get_issue_comments.return_value = [comment]
    assert _find_existing_comment(pull) is comment


@patch("reviewer.poster.Github")
def test_post_review_edits_existing_comment(mock_github):
    existing = MagicMock()
    existing.body = "## AI Code Review\nold content"
    pull = MagicMock()
    pull.get_issue_comments.return_value = [existing]
    mock_github.return_value.get_repo.return_value.get_pull.return_value = pull

    post_review(REVIEW, "owner/repo", 1, "abc1234", "token", False)

    existing.edit.assert_called_once()
    pull.create_issue_comment.assert_not_called()


@patch("reviewer.poster.Github")
def test_post_review_creates_new_comment_when_none_exists(mock_github):
    pull = MagicMock()
    pull.get_issue_comments.return_value = []
    mock_github.return_value.get_repo.return_value.get_pull.return_value = pull

    post_review(REVIEW, "owner/repo", 1, "abc1234", "token", False)

    pull.create_issue_comment.assert_called_once()


@patch("reviewer.poster.Github")
def test_post_review_raises_github_exception_on_403(mock_github):
    pull = MagicMock()
    pull.get_issue_comments.return_value = []
    pull.create_issue_comment.side_effect = GithubException(403, {"message": "Forbidden"}, None)
    mock_github.return_value.get_repo.return_value.get_pull.return_value = pull

    with pytest.raises(GithubException) as exc_info:
        post_review(REVIEW, "owner/repo", 1, "abc1234", "token", False)
    assert exc_info.value.status == 403
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_poster.py -v
```

Expected: `ModuleNotFoundError` — `poster` does not exist yet.

- [ ] **Step 3: Create `reviewer/poster.py`**

```python
from github import Github

SECTION_LABELS = [
    ("### Bugs", "bugs"),
    ("### Security", "security"),
    ("### Code Quality", "code_quality"),
    ("### Suggestions", "suggestions"),
]


def post_review(
    review: dict,
    repo: str,
    pr_number: int,
    sha: str,
    token: str,
    truncated: bool,
) -> None:
    """Post or update the AI review comment on the PR."""
    body = _build_comment(review, sha, truncated)
    g = Github(token)
    pull = g.get_repo(repo).get_pull(pr_number)
    existing = _find_existing_comment(pull)
    if existing:
        existing.edit(body)
    else:
        pull.create_issue_comment(body)


def _build_comment(review: dict, sha: str, truncated: bool) -> str:
    """Assemble the final markdown comment body from the review dict."""
    lines = [
        "## AI Code Review",
        "",
        "**Model:** claude-opus-4-6",
        f"**Commit:** {sha[:7]}",
        "",
    ]
    if truncated:
        lines += ["> Diff truncated — showing largest changed files only.", ""]
    for heading, key in SECTION_LABELS:
        lines.append(heading)
        for item in review[key]:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _find_existing_comment(pull):
    """Find a previously posted AI review comment in the PR's issue comment thread."""
    for comment in pull.get_issue_comments():
        if comment.body.lstrip().startswith("## AI Code Review"):
            return comment
    return None
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_poster.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Run all tests so far**

```bash
pytest -v
```

Expected: All tests across all files pass.

- [ ] **Step 6: Commit**

```bash
git add reviewer/poster.py tests/test_poster.py
git commit -m "feat: add poster to publish or update PR review comment"
```

---

## Chunk 4: Main + GitHub Actions + README

### Task 7: main.py — orchestration, truncation, error handling

**Files:**
- Create: `reviewer/main.py`
- Create: `tests/test_main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_main.py`:

```python
import sys
import anthropic
import httpx
import pytest
from unittest.mock import MagicMock, patch
from reviewer.main import _get_env, _truncate_diff, _split_diff_by_file

ENV_VARS = {
    "ANTHROPIC_API_KEY": "key",
    "GITHUB_TOKEN": "token",
    "PR_NUMBER": "1",
    "REPO": "owner/repo",
    "PR_SHA": "abc1234",
}


# --- _get_env ---

def test_get_env_returns_all_vars(monkeypatch):
    for k, v in ENV_VARS.items():
        monkeypatch.setenv(k, v)
    env = _get_env()
    assert env["ANTHROPIC_API_KEY"] == "key"
    assert env["PR_NUMBER"] == 1
    assert env["REPO"] == "owner/repo"


def test_get_env_exits_on_missing_var(monkeypatch):
    for key in ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SystemExit):
        _get_env()


# --- _split_diff_by_file ---

def test_split_diff_splits_two_files():
    diff = (
        "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x\n+y\n"
        "--- a/bar.py\n+++ b/bar.py\n@@ -1 +1 @@\n-a\n+b"
    )
    parts = _split_diff_by_file(diff)
    assert len(parts) == 2
    assert "foo.py" in parts[0]
    assert "bar.py" in parts[1]


def test_split_diff_single_file():
    diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x\n+y"
    parts = _split_diff_by_file(diff)
    assert len(parts) == 1


# --- _truncate_diff ---

@patch("reviewer.main.anthropic.Anthropic")
def test_truncate_diff_returns_unmodified_when_under_limit(mock_client_class):
    mock_client_class.return_value.messages.count_tokens.return_value = MagicMock(input_tokens=100)
    pr_data = {"diff": "small diff", "title": "t", "body": "b", "files": []}
    result, truncated = _truncate_diff(pr_data, "key")
    assert result["diff"] == "small diff"
    assert truncated is False


@patch("reviewer.main.anthropic.Anthropic")
def test_truncate_diff_truncates_when_over_limit(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_client.messages.count_tokens.side_effect = [
        MagicMock(input_tokens=9000),  # full diff — over limit
        MagicMock(input_tokens=4000),  # first file accumulation — fits
        MagicMock(input_tokens=9000),  # second file — would exceed
    ]
    pr_data = {
        "diff": (
            "--- a/big.py\n+++ b/big.py\n" + "-x\n+y\n" * 50
            + "\n--- a/small.py\n+++ b/small.py\n-a\n+b"
        ),
        "title": "t", "body": "b", "files": [],
    }
    result, truncated = _truncate_diff(pr_data, "key")
    assert truncated is True
    assert "small.py" not in result["diff"]


# --- main() orchestration ---

@patch("reviewer.main.post_review")
@patch("reviewer.main.format_review", return_value={"bugs": [], "security": [], "code_quality": [], "suggestions": []})
@patch("reviewer.main.analyze", return_value="### Bugs\n- No issues found.")
@patch("reviewer.main.fetch_pr_data", return_value={"title": "t", "body": "b", "files": ["f.py"], "diff": "some diff"})
@patch("reviewer.main.anthropic.Anthropic")
def test_main_happy_path_exits_zero(mock_client, mock_fetch, mock_analyze, mock_format, mock_post, monkeypatch):
    for k, v in ENV_VARS.items():
        monkeypatch.setenv(k, v)
    mock_client.return_value.messages.count_tokens.return_value = MagicMock(input_tokens=100)

    from reviewer.main import main
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    mock_fetch.assert_called_once()
    mock_analyze.assert_called_once()
    mock_format.assert_called_once()
    mock_post.assert_called_once()


@patch("reviewer.main._post_fallback")
@patch("reviewer.main.anthropic.Anthropic")
def test_main_posts_fallback_on_claude_error(mock_client, mock_fallback, monkeypatch):
    for k, v in ENV_VARS.items():
        monkeypatch.setenv(k, v)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    api_error = anthropic.APIConnectionError(request=request)

    mock_client.return_value.messages.count_tokens.return_value = MagicMock(input_tokens=100)

    with patch("reviewer.main.fetch_pr_data", return_value={"title": "t", "body": "b", "files": ["f.py"], "diff": "diff"}):
        with patch("reviewer.main.analyze", side_effect=api_error):
            from reviewer.main import main
            with pytest.raises(SystemExit) as exc_info:
                main()
    assert exc_info.value.code == 1
    mock_fallback.assert_called_once()
    assert "Claude API error" in mock_fallback.call_args[0][1]


@patch("reviewer.main._post_fallback")
@patch("reviewer.main.fetch_pr_data", return_value={"title": "t", "body": "b", "files": [], "diff": ""})
@patch("reviewer.main.anthropic.Anthropic")
def test_main_exits_cleanly_on_empty_diff(mock_client, mock_fetch, mock_fallback, monkeypatch):
    for k, v in ENV_VARS.items():
        monkeypatch.setenv(k, v)
    mock_client.return_value.messages.count_tokens.return_value = MagicMock(input_tokens=0)

    from reviewer.main import main
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    mock_fallback.assert_called_once()
    assert "No code changes" in mock_fallback.call_args[0][1]
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError` — `main` does not exist yet.

- [ ] **Step 3: Create `reviewer/main.py`**

```python
import os
import sys
import time
import logging
import anthropic
from github import GithubException

from reviewer.fetcher import fetch_pr_data
from reviewer.analyzer import analyze
from reviewer.formatter import format_review
from reviewer.poster import post_review

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _get_env() -> dict:
    """Read and validate all five required environment variables."""
    required = ["ANTHROPIC_API_KEY", "GITHUB_TOKEN", "PR_NUMBER", "REPO", "PR_SHA"]
    env = {}
    missing = []
    for key in required:
        val = os.environ.get(key)
        if not val:
            missing.append(key)
        else:
            env[key] = val
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    env["PR_NUMBER"] = int(env["PR_NUMBER"])
    return env


def _split_diff_by_file(diff: str) -> list[str]:
    """Split a unified diff string into per-file sections."""
    sections = []
    current: list[str] = []
    for line in diff.splitlines():
        if line.startswith("--- a/") and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    return sections


def _truncate_diff(pr_data: dict, api_key: str) -> tuple[dict, bool]:
    """Truncate diff to 8,000 token budget if needed. Owned by main.py."""
    client = anthropic.Anthropic(api_key=api_key)
    diff = pr_data["diff"]

    result = client.messages.count_tokens(
        model="claude-opus-4-6",
        messages=[{"role": "user", "content": diff}],
    )
    if result.input_tokens <= 8000:
        return pr_data, False

    file_diffs = _split_diff_by_file(diff)
    file_diffs.sort(key=lambda x: x.count("\n"), reverse=True)

    accumulated = ""
    for file_diff in file_diffs:
        candidate = (accumulated + "\n" + file_diff).lstrip() if accumulated else file_diff
        check = client.messages.count_tokens(
            model="claude-opus-4-6",
            messages=[{"role": "user", "content": candidate}],
        )
        if check.input_tokens > 8000:
            break
        accumulated = candidate

    return {**pr_data, "diff": accumulated}, True


def _post_fallback(env: dict, message: str) -> None:
    """Post a plain fallback message to the PR."""
    from github import Github
    try:
        g = Github(env["GITHUB_TOKEN"])
        pull = g.get_repo(env["REPO"]).get_pull(env["PR_NUMBER"])
        pull.create_issue_comment(message)
    except Exception as e:
        logging.error(f"Failed to post fallback comment: {e}")


def main() -> None:
    env = _get_env()

    logging.info(f"Fetching PR #{env['PR_NUMBER']} from {env['REPO']}")
    try:
        pr_data = fetch_pr_data(env["REPO"], env["PR_NUMBER"], env["GITHUB_TOKEN"])
    except GithubException:
        time.sleep(2)
        try:
            pr_data = fetch_pr_data(env["REPO"], env["PR_NUMBER"], env["GITHUB_TOKEN"])
        except GithubException as e:
            logging.error(f"GitHub API fetch failed after retry: {e}")
            sys.exit(1)

    if not pr_data["diff"].strip():
        logging.info("No code changes detected.")
        _post_fallback(env, "No code changes detected — skipping review.")
        sys.exit(0)

    pr_data, truncated = _truncate_diff(pr_data, env["ANTHROPIC_API_KEY"])

    try:
        logging.info("Analyzing PR with Claude...")
        raw_review = analyze(pr_data, env["ANTHROPIC_API_KEY"])
    except anthropic.APIError as e:
        logging.error(f"Claude API error after retries: {e}")
        _post_fallback(env, "Review failed: Claude API error. Check Actions logs.")
        sys.exit(1)

    review = format_review(raw_review)

    try:
        post_review(
            review,
            env["REPO"],
            env["PR_NUMBER"],
            env["PR_SHA"],
            env["GITHUB_TOKEN"],
            truncated,
        )
    except GithubException as e:
        if e.status == 403:
            print(
                "Review skipped: insufficient permissions to post comment. "
                "Check that GITHUB_TOKEN has pull-requests: write scope."
            )
            sys.exit(1)
        time.sleep(2)
        try:
            post_review(review, env["REPO"], env["PR_NUMBER"], env["PR_SHA"], env["GITHUB_TOKEN"], truncated)
        except GithubException:
            logging.error(f"GitHub API retry failed: {e}")
            sys.exit(1)

    logging.info("Review posted successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_main.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: All tests across all files pass.

- [ ] **Step 6: Commit**

```bash
git add reviewer/main.py tests/test_main.py
git commit -m "feat: add main orchestrator with truncation and error handling"
```

---

### Task 8: GitHub Actions files

**Files:**
- Create: `action.yml`
- Create: `.github/workflows/review.yml`
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Create `action.yml`**

```yaml
name: PR Reviewer
description: AI-powered PR review using Claude Opus
inputs:
  anthropic_api_key:
    description: Anthropic API key
    required: true
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - run: pip install --upgrade pip && pip install -r ${{ github.action_path }}/requirements.txt
      shell: bash
    - run: python ${{ github.action_path }}/reviewer/main.py
      shell: bash
      env:
        ANTHROPIC_API_KEY: ${{ inputs.anthropic_api_key }}
        GITHUB_TOKEN: ${{ github.token }}
        PR_NUMBER: ${{ github.event.pull_request.number }}
        REPO: ${{ github.repository }}
        PR_SHA: ${{ github.event.pull_request.head.sha }}
```

- [ ] **Step 2: Create `.github/workflows/review.yml`**

```yaml
name: PR Review

on:
  workflow_call:
    secrets:
      ANTHROPIC_API_KEY:
        required: true

permissions:
  pull-requests: write
  contents: read

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

- [ ] **Step 3: Create `.github/workflows/test.yml`**

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install --upgrade pip && pip install -r requirements.txt
      - run: pytest
```

- [ ] **Step 4: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('action.yml'))" && echo "action.yml OK"
python -c "import yaml; yaml.safe_load(open('.github/workflows/review.yml'))" && echo "review.yml OK"
python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))" && echo "test.yml OK"
```

Expected: All three print "OK".

- [ ] **Step 5: Commit**

```bash
git add action.yml .github/workflows/review.yml .github/workflows/test.yml
git commit -m "feat: add GitHub Actions composite action and reusable workflow"
```

---

### Task 9: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# pr-reviewer

AI-powered GitHub PR reviewer using Claude Opus. Drops into any repo in 2 steps.

![Tests](https://github.com/YOUR_USERNAME/pr-reviewer/actions/workflows/test.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Model](https://img.shields.io/badge/model-claude--opus--4--6-orange)
![License](https://img.shields.io/badge/license-MIT-green)

## What it does

When a pull request is opened or updated, this action fetches the diff, sends it to Claude Opus
with an embedded code review and security checklist, and posts a structured review comment with
four sections: Bugs, Security, Code Quality, and Suggestions. The comment is updated in-place on
every new commit to the PR.

## Quick start

**Step 1:** Add `ANTHROPIC_API_KEY` to your repo secrets
(Settings → Secrets and variables → Actions → New repository secret).

**Step 2:** Add this file to `.github/workflows/pr-review.yml` in your repo:

    on: [pull_request]
    jobs:
      review:
        uses: YOUR_USERNAME/pr-reviewer/.github/workflows/review.yml@v1
        secrets:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

## How it works

```mermaid
flowchart LR
    A[PR Opened] --> B[fetcher.py\nGitHub API\ngets diff]
    B --> C[analyzer.py\nClaude Opus\nreviews diff]
    C --> D[formatter.py\nstructures\n4 sections]
    D --> E[poster.py\nposts PR\ncomment]
    style A fill:#ddf4ff,stroke:#0550ae
    style B fill:#fff8c5,stroke:#9a6700
    style C fill:#ffebe9,stroke:#cf222e
    style D fill:#dafbe1,stroke:#116329
    style E fill:#fbefff,stroke:#8250df
```

## Project structure

```
reviewer/
├── main.py       # orchestrates the pipeline
├── fetcher.py    # fetches PR diff from GitHub API
├── analyzer.py   # sends diff to Claude Opus
├── formatter.py  # parses response into 4 sections
├── poster.py     # posts or updates PR comment
└── prompts.py    # system prompt + user prompt builder
tests/            # pytest suite — all API calls mocked
action.yml        # composite action definition
.github/
└── workflows/
    ├── review.yml  # reusable workflow (what target repos call)
    └── test.yml    # CI: runs pytest on push
```

## Local development

```bash
git clone https://github.com/YOUR_USERNAME/pr-reviewer
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
pytest
```

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GITHUB_TOKEN` | GitHub personal access token with `repo` scope |
| `PR_NUMBER` | PR number to review |
| `REPO` | Repository in `owner/repo` format |
| `PR_SHA` | Commit SHA of the PR head |

## License

MIT
```

- [ ] **Step 2: Replace `YOUR_USERNAME` with your GitHub username throughout `README.md`**

The README contains `YOUR_USERNAME` in 3 places: the badge URL, the workflow `uses:` line, and the clone URL. Replace all three. Verify with:

```bash
grep "YOUR_USERNAME" README.md
```

Expected: no output (all occurrences replaced).

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest -v
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add README with Mermaid diagram and quick start"
```

- [ ] **Step 5: Tag v1**

```bash
git tag v1
git push origin main --tags
```

---
