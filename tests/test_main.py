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
