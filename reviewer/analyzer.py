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
