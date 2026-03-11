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
