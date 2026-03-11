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
    file_diffs.sort(
        key=lambda x: sum(1 for l in x.splitlines() if l.startswith(("+", "-")) and not l.startswith(("---", "+++"))),
        reverse=True,
    )

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
        except GithubException as retry_e:
            logging.error(f"GitHub API retry failed: {retry_e}")
            sys.exit(1)

    logging.info("Review posted successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
