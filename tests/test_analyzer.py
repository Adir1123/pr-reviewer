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
