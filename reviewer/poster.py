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
