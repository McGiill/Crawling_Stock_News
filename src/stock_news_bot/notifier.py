from __future__ import annotations

import requests


def send_discord_message(webhook_url: str, content: str, timeout_seconds: int) -> None:
    response = requests.post(
        webhook_url,
        json={"content": content},
        timeout=timeout_seconds,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
