from __future__ import annotations

import sys
from datetime import datetime, timezone

from stock_news_bot.config import load_settings
from stock_news_bot.dedupe import SentArticleStore
from stock_news_bot.fetcher import NewsItem, fetch_news
from stock_news_bot.notifier import send_discord_message
from stock_news_bot.summarizer import summarize_symbol_news


def build_message(
    *,
    symbol: str,
    headline: str,
    summary_lines: list[str],
    sentiment: str,
    reason: str,
    articles: list[NewsItem],
) -> str:
    summary_block = "\n".join(f"- {line}" for line in summary_lines)
    article_block = "\n".join(f"- {article.title} ({article.url})" for article in articles[:5])
    return (
        f"## {symbol} 뉴스 브리핑\n"
        f"핵심 이슈: {headline}\n"
        f"판단: {sentiment}\n"
        f"근거: {reason}\n"
        f"요약:\n{summary_block}\n"
        f"참고 기사:\n{article_block}"
    )


def main() -> int:
    settings = load_settings()
    store = SentArticleStore(settings.sent_articles_path)

    total_sent = 0
    for symbol in settings.watchlist:
        items = fetch_news(
            symbol=symbol,
            max_items=settings.max_articles_per_symbol,
            timeout_seconds=settings.request_timeout_seconds,
        )

        new_items = [
            item
            for item in items
            if item.article_text and not store.has(item.url)
        ]
        if not new_items:
            continue

        try:
            summary = summarize_symbol_news(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                symbol=symbol,
                articles=new_items,
            )
            message = build_message(
                symbol=symbol,
                headline=summary.headline,
                summary_lines=summary.summary_lines,
                sentiment=summary.sentiment,
                reason=summary.reason,
                articles=new_items,
            )
            send_discord_message(
                webhook_url=settings.discord_webhook_url,
                content=message,
                timeout_seconds=settings.request_timeout_seconds,
            )
        except Exception as exc:
            print(f"[ERROR] Failed to process symbol: {symbol} ({exc})", file=sys.stderr)
            continue

        sent_at = datetime.now(timezone.utc).isoformat()
        for item in new_items:
            store.add(
                item.url,
                {
                    "symbol": item.symbol,
                    "title": item.title,
                    "source": item.source,
                    "published_at": item.published_at,
                    "sent_at": sent_at,
                },
            )
        total_sent += 1

    print(f"[INFO] Completed run. Sent {total_sent} symbol briefing(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
