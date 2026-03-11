# GitHub PR AI Reviewer — Design Spec

**Date:** 2026-03-11
**Status:** Approved

---

## Overview

A reusable GitHub Actions workflow + Python package that automatically reviews pull requests using Claude Opus. When a PR is opened or updated, the system fetches the diff, analyzes it with an LLM using embedded code review and security checklists, and posts a structured 4-section review comment on the PR.

Designed to be installed in any GitHub repo with a 5-line workflow file. Built as a portfolio project demonstrating AI integration, automation, and software engineering best practices.

---

## Goals

- **Primary:** Portfolio project showcasing AI + GitHub automation skills to recruiters
- **Secondary:** Real-world usability — installable in any repo with minimal setup
- **Non-goal:** A hosted service or GitHub App; this runs entirely in GitHub Actions

---

## Architecture

### Trigger

GitHub Actions `pull_request` event (opened, synchronize, reopened).

### Two-repo model

- **`pr-reviewer` repo** — the published action + Python package (this project)
- **Any target repo** — adds a 5-line workflow file that calls `pr-reviewer` as a reusable workflow

### Data flow

```
PR Opened → GitHub Actions → fetcher.py → analyzer.py → formatter.py → poster.py → PR comment
```

1. `pull_request` event fires in target repo
2. Reusable workflow at `your-username/pr-reviewer/.github/workflows/review.yml@v1` is invoked
3. `fetcher.py` calls GitHub API to get the PR diff and changed file list (returns full diff, no truncation)
4. `main.py` checks diff token count and truncates if needed before passing to `analyzer.py`
5. `analyzer.py` sends diff + PR context to Claude Opus with system prompt containing embedded checklists
6. `formatter.py` parses Claude's response into 4 structured sections
7. `poster.py` searches for an existing review comment on the PR; replaces it if found, creates a new one if not
8. The PR shows one review comment per PR, updated on each new commit

### Reusable workflow interface (`review.yml`)

Full `review.yml` (lives in this repo at `.github/workflows/review.yml`):

```yaml
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
      - uses: your-username/pr-reviewer@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

`GITHUB_TOKEN` is automatically available in every Actions run — target repos do not need to configure it.

`permissions: pull-requests: write` is required so `poster.py` can post comments. Note: reusable workflows called from a forked PR inherit the caller's permissions. If a fork-originated PR triggers this workflow, it receives a read-only token by default and comment posting will fail — see Error Handling.

What target repos add (2 steps total):

```yaml
# .github/workflows/pr-review.yml
on: [pull_request]
jobs:
  review:
    uses: your-username/pr-reviewer/.github/workflows/review.yml@v1
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### `action.yml` — composite action

The composite action installs dependencies and runs `main.py`. Skeleton:

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
    - run: pip install -r requirements.txt
      shell: bash
    - run: python reviewer/main.py
      shell: bash
      env:
        ANTHROPIC_API_KEY: ${{ inputs.anthropic_api_key }}
        GITHUB_TOKEN: ${{ github.token }}
        PR_NUMBER: ${{ github.event.pull_request.number }}
        REPO: ${{ github.repository }}
        PR_SHA: ${{ github.event.pull_request.head.sha }}
```

### Environment variable contract

`main.py` reads these environment variables at startup. All five are validated before any API call.

| Variable | Source | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Repo secret, passed via action input | Yes |
| `GITHUB_TOKEN` | Auto-injected by GitHub Actions | Yes |
| `PR_NUMBER` | `github.event.pull_request.number` | Yes |
| `REPO` | `github.repository` (format: `owner/repo`) | Yes |
| `PR_SHA` | `github.event.pull_request.head.sha` | Yes |

`PR_SHA` is included in the posted comment footer so readers know which commit was reviewed.

For local development, these are loaded from `.env` via `python-dotenv`.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12 |
| LLM | `claude-opus-4-6` via `anthropic` SDK |
| GitHub API | `PyGithub` |
| CI/CD | GitHub Actions (reusable workflow) |
| Testing | `pytest` + `pytest-mock` |
| Local dev | `python-dotenv` |
| Docs diagrams | Mermaid (rendered natively in GitHub README) |

---

## Repository Structure

```
pr-reviewer/
├── .github/
│   └── workflows/
│       ├── review.yml        # reusable workflow (entry point for target repos)
│       └── test.yml          # CI: runs pytest on every push to main
├── reviewer/                 # Python package
│   ├── main.py               # orchestrates the 4-step pipeline
│   ├── fetcher.py            # fetches and truncates PR diff from GitHub API
│   ├── analyzer.py           # sends diff to Claude Opus, returns raw review
│   ├── formatter.py          # parses raw review into 4 structured sections
│   ├── poster.py             # posts or replaces review comment on GitHub PR
│   └── prompts.py            # system prompt + user prompt builder
├── tests/
│   ├── test_fetcher.py
│   ├── test_analyzer.py
│   ├── test_formatter.py
│   ├── test_poster.py
│   ├── test_prompts.py
│   └── test_main.py
├── action.yml                # composite action definition
├── requirements.txt
├── .env.example
└── README.md
```

---

## Prompt Strategy

`prompts.py` contains three components:

### SYSTEM_PROMPT

Sets Claude's role as a senior code reviewer and enforces the output format. Embeds two structured checklists:

**Code review checklist** (drawn from code-review patterns):
- Naming clarity, function length, complexity
- Dead code, unused imports
- Error handling at system boundaries
- Test coverage of new logic
- Separation of concerns

**Security checklist** (drawn from security-guidance / OWASP Top 10):
- SQL/command injection via string interpolation
- Hardcoded secrets or API keys
- Insecure deserialization
- Missing input validation at system boundaries
- Auth/permission checks
- Sensitive data in logs

Output format enforced by system prompt (use `###` heading level exactly):
```
### Bugs
### Security
### Code Quality
### Suggestions
```
Each section uses bullet points. If no issues: "No issues found."

### build_user_prompt(pr_title, pr_body, file_list, diff)

Dynamically constructs the user message with PR context injected. If `pr_body` is `None` or empty, substitute the string `"No description provided."`.

---

## Module Interface Contracts

| Module | Input | Returns |
|---|---|---|
| `fetcher.py` | `repo: str`, `pr_number: int`, `token: str` | `dict` with keys `title: str`, `body: str` (never None — empty string if GitHub returns null), `files: list[str]`, `diff: str` (full diff, no truncation) |
| `main.py` (truncation step) | `pr_data: dict`, `api_key: str` | Calls `result = client.messages.count_tokens(...)`. Checks `result.input_tokens`. If over 8,000, sorts file diffs by changed-line count descending, rebuilds diff by accumulating files until `result.input_tokens` would exceed 8,000 (re-calling `count_tokens` after each addition), sets `truncated = True`. Passes updated `pr_data` and `truncated` flag forward. |
| `analyzer.py` | `pr_data: dict`, `api_key: str` | `str` — raw Claude response text. Raises `anthropic.APIError` if retries exhausted. `analyzer.py` imports `prompts.py` directly and calls `SYSTEM_PROMPT` and `build_user_prompt()` internally. `main.py` does not construct prompts — it passes raw `pr_data`. |
| `formatter.py` | `raw: str` | `dict` with keys `bugs`, `security`, `code_quality`, `suggestions` each a `list[str]`. Parsed by iterating line-by-line; a line matching `re.match(r'^### (Bugs|Security|Code Quality|Suggestions)', line)` starts a new section. Any text before the first matching heading is discarded. Missing sections default to `["No issues found."]`. Fully malformed input (no matching headings at all) → all four sections as `["No issues found."]`, log a warning. |
| `poster.py` | `review: dict`, `repo: str`, `pr_number: int`, `sha: str`, `token: str`, `truncated: bool` | `None` — side effect only. `poster.py` owns assembly of the final markdown comment body from the `review` dict, using the format defined in "Review Output Format". |

**Truncation is owned by `main.py`.** Algorithm (executed between `fetcher.py` and `analyzer.py`):
1. Call `result = client.messages.count_tokens(model="claude-opus-4-6", messages=[{"role": "user", "content": diff}])` once on the full combined diff string. Token count is `result.input_tokens`.
2. If `result.input_tokens` ≤ 8,000: pass diff to `analyzer.py` as-is, `truncated = False`.
3. If `result.input_tokens` > 8,000: sort individual file diffs by changed-line count descending. Rebuild the diff string by appending file diffs one by one; after each addition, call `count_tokens()` and check `result.input_tokens`. Stop before adding a file that would push the total over 8,000. Pass accumulated diff to `analyzer.py`, `truncated = True`.
4. In the worst case this makes N SDK calls. In practice diffs are small and truncation is rare.

The 8,000-token budget is for the **diff portion only**. The system prompt + user prompt header adds ~2,000 tokens, keeping the full request well within claude-opus-4-6's context window.

`main.py` passes `truncated` to `poster.py`, which prepends the truncation notice to the comment if `True`.

---

## Review Output Format

Posted as a single GitHub PR comment in markdown:

```markdown
## AI Code Review

**Model:** claude-opus-4-6
**Commit:** abc1234

### Bugs
- <findings or "No issues found.">

### Security
- <findings or "No issues found.">

### Code Quality
- <findings or "No issues found.">

### Suggestions
- <findings or "No issues found.">
```

If diff was truncated, the following line is prepended before the sections:

```
> Diff truncated — showing largest changed files only.
```

No emojis in output.

---

## Duplicate Comment Policy

On every `pull_request` event (including `synchronize` — i.e. new commits pushed to the PR):

- `poster.py` searches the PR's **issue comments** (general comment thread) using `pull_request.get_issue_comments()` — not review comments (inline diff comments)
- Search: find the first comment whose body, after stripping leading whitespace, starts with `"## AI Code Review"` (case-sensitive: `body.lstrip().startswith("## AI Code Review")`)
- If found: edit the existing comment in-place using `comment.edit(new_body)`. The new body still starts with `"## AI Code Review"` so future detections work correctly.
- If not found: create a new issue comment

Result: each PR always shows exactly one review comment, updated with each new push.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Diff exceeds 8,000 tokens | `main.py` truncates to largest files that fit (see truncation algorithm in Module Interface Contracts); sets `truncated = True`; `poster.py` prepends truncation notice to comment |
| Claude API failure | Catch `anthropic.RateLimitError` first: parse wait duration with `try: wait = int(float(e.response.headers.get("retry-after", 60))) except (ValueError, TypeError): wait = 60`, then sleep and retry once. (The `retry-after` header may be absent, an integer string, a decimal string, or an HTTP-date — the `float()` intermediate handles decimal strings; all other formats fall back to 60s.) Catch all other `anthropic.APIError` next: retry once after 2 seconds. If still failing after retry, `analyzer.py` raises the exception; `main.py` catches it and calls `poster.py` with fallback body: "Review failed: Claude API error. Check Actions logs." |
| GitHub API failure | Catch `GithubException`, retry once after 2 seconds. If still failing, exit non-zero (Actions step shows as failed) |
| GitHub 403 on comment post | Catch `GithubException` with status 403 when posting; exit non-zero with message: "Review skipped: insufficient permissions to post comment. Check that GITHUB_TOKEN has pull-requests: write scope." |
| Missing env variables | Validate all 5 at startup, fail fast with clear message before any API call |
| Empty diff | Post: "No code changes detected — skipping review." Exit cleanly |

---

## Local Development

`.env.example` must contain:

```
ANTHROPIC_API_KEY=your_key_here
GITHUB_TOKEN=your_personal_access_token
PR_NUMBER=1
REPO=owner/repo
PR_SHA=abc1234
```

### `requirements.txt`

Pin to minimum compatible versions using `>=`:

```
anthropic>=0.40.0
PyGithub>=2.3.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

---

## Testing

| File | Strategy |
|---|---|
| `test_fetcher.py` | Mock PyGithub responses; assert diff extraction, correct `title`/`body`/`files`/`diff` keys returned; assert `body` is `""` when GitHub returns null |
| `test_analyzer.py` | Mock `anthropic` SDK; assert prompt construction includes title, body, file list, and diff; assert `RateLimitError` triggers `int(header)` sleep + one retry; assert other `APIError` triggers 2s sleep + one retry; assert exception is re-raised after retry exhausted (fallback posting is tested in `test_main.py`) |
| `test_main.py` | Mock all modules + Anthropic client; assert truncation logic (token count, file sorting, `truncated` flag); assert fallback comment posted when `analyzer.py` raises; assert `sys.exit(0)` on success |
| `test_formatter.py` | No mocks — pure string parsing; covers `###`-prefixed sections, missing sections, empty sections, extra whitespace, fully malformed input |
| `test_poster.py` | Mock PyGithub; assert `body.lstrip().startswith()` detection; existing comment edited when found, new comment created when not; truncation notice prepended when `truncated=True` |
| `test_prompts.py` | Assert security and code review checklist items present in system prompt; assert `###` heading format in enforced output block |

CI runs `pytest` on every push to `main`. README shows a passing badge.

### CI workflow (`test.yml`) skeleton

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

---

## README Structure

1. Project title + one-line description
2. Badges: tests passing, Python version, model, license
3. What it does (2–3 sentences)
4. Quick start (2 steps)
5. How it works — Mermaid `flowchart LR` diagram
6. Project structure — code block
7. Local development instructions
8. License

---

## Versioning

The `v1` tag is a git tag pushed manually to this repo after the first stable release — there is no automated release workflow. To release:

```bash
git tag v1
git push origin v1
```

Target repos pin to `@v1`. To release a new major version: push a `v2` tag. The `v1` tag is never force-moved — backwards compatibility is maintained per major version.

---

## Skills Demonstrated

- LLM integration with structured prompt engineering
- GitHub Actions authoring (reusable workflows, composite actions)
- Python package design with clear module boundaries
- API integration (Anthropic SDK, PyGithub)
- Test-driven development with mocked external APIs
- CI/CD pipeline setup
- Security-aware design (checklist-driven prompts, fail-fast validation)
