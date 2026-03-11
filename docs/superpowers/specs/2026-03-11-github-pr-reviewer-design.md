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
3. `fetcher.py` calls GitHub API to get the PR diff and changed file list
4. `analyzer.py` sends diff + PR context to Claude Opus with system prompt containing embedded checklists
5. `formatter.py` parses Claude's response into 4 structured sections
6. `poster.py` posts the formatted markdown comment on the PR via GitHub API

### Reusable workflow (what target repos add)

```yaml
# .github/workflows/pr-review.yml
on: [pull_request]
jobs:
  review:
    uses: your-username/pr-reviewer/.github/workflows/review.yml@v1
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

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
│   ├── fetcher.py            # fetches PR diff from GitHub API
│   ├── analyzer.py           # sends diff to Claude Opus, returns raw review
│   ├── formatter.py          # parses raw review into 4 structured sections
│   ├── poster.py             # posts formatted comment to GitHub PR
│   └── prompts.py            # system prompt + user prompt builder
├── tests/
│   ├── test_fetcher.py
│   ├── test_analyzer.py
│   ├── test_formatter.py
│   └── test_prompts.py
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

Output format enforced by system prompt:
```
## Bugs
## Security
## Code Quality
## Suggestions
```
Each section uses bullet points. If no issues: "No issues found."

### build_user_prompt(pr_title, pr_body, file_list, diff)

Dynamically constructs the user message with PR context injected.

---

## Review Output Format

Posted as a single GitHub PR comment in markdown:

```markdown
## AI Code Review

**Model:** claude-opus-4-6

### Bugs
- <findings or "No issues found.">

### Security
- <findings or "No issues found.">

### Code Quality
- <findings or "No issues found.">

### Suggestions
- <findings or "No issues found.">
```

No emojis in output.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Diff exceeds token limit | Truncate to top N files by change size; note truncation in comment |
| Claude API failure | Post comment: "Review failed: Claude API error. Check Actions logs." |
| GitHub API failure | Catch `GithubException`, exit non-zero (Actions step shows as failed) |
| Missing secrets | Validate at startup, fail fast with clear message before any API call |
| Empty diff | Post: "No code changes detected — skipping review." Exit cleanly |

---

## Testing

| File | Strategy |
|---|---|
| `test_fetcher.py` | Mock PyGithub responses; assert diff extraction and truncation logic |
| `test_analyzer.py` | Mock `anthropic` SDK; assert prompt construction includes all PR context |
| `test_formatter.py` | No mocks — pure string parsing; covers missing/empty sections |
| `test_prompts.py` | Assert security and code review checklist items present in system prompt |

CI runs `pytest` on every push to `main`. README shows a passing badge.

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

## Skills Demonstrated

- LLM integration with structured prompt engineering
- GitHub Actions authoring (reusable workflows, composite actions)
- Python package design with clear module boundaries
- API integration (Anthropic SDK, PyGithub)
- Test-driven development with mocked external APIs
- CI/CD pipeline setup
- Security-aware design (checklist-driven prompts, fail-fast validation)
