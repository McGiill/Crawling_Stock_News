from __future__ import annotations

import sys
from datetime import datetime, timezone

from stock_news_bot.config import load_settings
from stock_news_bot.dedupe import SentArticleStore
from stock_news_bot.fetcher import NewsItem
from stock_news_bot.market import collect_symbol_news
from stock_news_bot.notifier import send_discord_message
from stock_news_bot.summarizer import (
    summarize_market_overview,
    summarize_sector_overview,
    summarize_symbol_news,
)


def build_symbol_message(
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
        f"## {symbol} 관심종목 브리핑\n"
        f"핵심 이슈: {headline}\n"
        f"판단: {sentiment}\n"
        f"근거: {reason}\n"
        f"요약:\n{summary_block}\n"
        f"참고 기사:\n{article_block}"
    )


def build_market_message(
    *,
    headline: str,
    summary_lines: list[str],
    us_market: str,
    kr_market: str,
    exchange_rate: str,
    key_driver: str,
    risk_factor: str,
) -> str:
    summary_block = "\n".join(f"- {line}" for line in summary_lines)
    return (
        "## 미국/한국 시장 브리핑\n"
        f"핵심 흐름: {headline}\n"
        f"미국 시장: {us_market}\n"
        f"한국 시장: {kr_market}\n"
        f"환율: {exchange_rate}\n"
        f"핵심 동인: {key_driver}\n"
        f"리스크: {risk_factor}\n"
        f"요약:\n{summary_block}"
    )


def build_sector_message(
    *,
    headline: str,
    summary_lines: list[str],
    strong_sectors: list[str],
    weak_sectors: list[str],
) -> str:
    summary_block = "\n".join(f"- {line}" for line in summary_lines)
    strong_block = "\n".join(f"- {item}" for item in strong_sectors)
    weak_block = "\n".join(f"- {item}" for item in weak_sectors)
    return (
        "## 강한 섹터 / 약한 섹터\n"
        f"핵심 흐름: {headline}\n"
        f"요약:\n{summary_block}\n"
        f"강한 섹터:\n{strong_block}\n"
        f"약한 섹터:\n{weak_block}"
    )


def _filter_new_items(store: SentArticleStore, items: list[NewsItem]) -> list[NewsItem]:
    return [item for item in items if item.article_text and not store.has(item.url)]


def _mark_items_as_sent(store: SentArticleStore, items: list[NewsItem]) -> None:
    sent_at = datetime.now(timezone.utc).isoformat()
    for item in items:
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


def main() -> int:
    settings = load_settings()
    store = SentArticleStore(settings.sent_articles_path)

    total_sent = 0

    try:
        print("[INFO] Collecting US/KR market news...")
        us_market_articles = collect_symbol_news(
            symbols=settings.us_market_symbols,
            max_items_per_symbol=settings.max_market_articles_per_symbol,
            timeout_seconds=settings.request_timeout_seconds,
        )
        kr_market_articles = collect_symbol_news(
            symbols=settings.kr_market_symbols,
            max_items_per_symbol=settings.max_market_articles_per_symbol,
            timeout_seconds=settings.request_timeout_seconds,
        )
        new_us_market_articles = {
            symbol: _filter_new_items(store, items)
            for symbol, items in us_market_articles.items()
        }
        new_kr_market_articles = {
            symbol: _filter_new_items(store, items)
            for symbol, items in kr_market_articles.items()
        }
        market_items_to_mark = [
            item
            for items in list(new_us_market_articles.values()) + list(new_kr_market_articles.values())
            for item in items
        ]
        if market_items_to_mark:
            market_summary = summarize_market_overview(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                us_articles_by_symbol={key: value for key, value in new_us_market_articles.items() if value},
                kr_articles_by_symbol={key: value for key, value in new_kr_market_articles.items() if value},
            )
            send_discord_message(
                webhook_url=settings.discord_webhook_url,
                content=build_market_message(
                    headline=market_summary.headline,
                    summary_lines=market_summary.summary_lines,
                    us_market=market_summary.us_market,
                    kr_market=market_summary.kr_market,
                    exchange_rate=market_summary.exchange_rate,
                    key_driver=market_summary.key_driver,
                    risk_factor=market_summary.risk_factor,
                ),
                timeout_seconds=settings.request_timeout_seconds,
            )
            _mark_items_as_sent(store, market_items_to_mark)
            total_sent += 1
            print(f"[INFO] Sent market briefing with {len(market_items_to_mark)} new article(s).")
        else:
            print("[INFO] Skipped market briefing: no new market articles.")
    except Exception as exc:
        print(f"[ERROR] Failed to process market briefing ({exc})", file=sys.stderr)

    try:
        print("[INFO] Collecting sector news...")
        sector_articles = collect_symbol_news(
            symbols=settings.sector_symbols,
            max_items_per_symbol=settings.max_sector_articles_per_symbol,
            timeout_seconds=settings.request_timeout_seconds,
        )
        new_sector_articles = {
            symbol: _filter_new_items(store, items)
            for symbol, items in sector_articles.items()
        }
        sector_items_to_mark = [item for items in new_sector_articles.values() for item in items]
        if sector_items_to_mark:
            sector_summary = summarize_sector_overview(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                sector_articles_by_symbol={key: value for key, value in new_sector_articles.items() if value},
            )
            send_discord_message(
                webhook_url=settings.discord_webhook_url,
                content=build_sector_message(
                    headline=sector_summary.headline,
                    summary_lines=sector_summary.summary_lines,
                    strong_sectors=sector_summary.strong_sectors,
                    weak_sectors=sector_summary.weak_sectors,
                ),
                timeout_seconds=settings.request_timeout_seconds,
            )
            _mark_items_as_sent(store, sector_items_to_mark)
            total_sent += 1
            print(f"[INFO] Sent sector briefing with {len(sector_items_to_mark)} new article(s).")
        else:
            print("[INFO] Skipped sector briefing: no new sector articles.")
    except Exception as exc:
        print(f"[ERROR] Failed to process sector briefing ({exc})", file=sys.stderr)

    print("[INFO] Collecting watchlist news...")
    for symbol in settings.watchlist:
        try:
            symbol_articles = collect_symbol_news(
                symbols=[symbol],
                max_items_per_symbol=settings.max_articles_per_symbol,
                timeout_seconds=settings.request_timeout_seconds,
            )
            new_items = _filter_new_items(store, symbol_articles.get(symbol, []))
            if not new_items:
                print(f"[INFO] Skipped {symbol}: no new watchlist articles.")
                continue

            summary = summarize_symbol_news(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                symbol=symbol,
                articles=new_items,
            )
            send_discord_message(
                webhook_url=settings.discord_webhook_url,
                content=build_symbol_message(
                    symbol=symbol,
                    headline=summary.headline,
                    summary_lines=summary.summary_lines,
                    sentiment=summary.sentiment,
                    reason=summary.reason,
                    articles=new_items,
                ),
                timeout_seconds=settings.request_timeout_seconds,
            )
            _mark_items_as_sent(store, new_items)
            total_sent += 1
            print(f"[INFO] Sent {symbol} briefing with {len(new_items)} new article(s).")
        except Exception as exc:
            print(f"[ERROR] Failed to process symbol: {symbol} ({exc})", file=sys.stderr)

    print(f"[INFO] Completed run. Sent {total_sent} briefing(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
