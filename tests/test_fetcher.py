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
