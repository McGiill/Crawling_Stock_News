from __future__ import annotations

from stock_news_bot.fetcher import NewsItem, fetch_news


def collect_symbol_news(
    *,
    symbols: list[str],
    max_items_per_symbol: int,
    timeout_seconds: int,
) -> dict[str, list[NewsItem]]:
    result: dict[str, list[NewsItem]] = {}
    for symbol in symbols:
        result[symbol] = fetch_news(
            symbol=symbol,
            max_items=max_items_per_symbol,
            timeout_seconds=timeout_seconds,
        )
    return result
