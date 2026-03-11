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
