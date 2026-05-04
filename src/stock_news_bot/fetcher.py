from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import requests
import trafilatura


RSS_URL_TEMPLATE = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"


@dataclass(frozen=True)
class NewsItem:
    symbol: str
    title: str
    url: str
    published_at: str
    source: str
    article_text: str


def fetch_news(symbol: str, max_items: int, timeout_seconds: int) -> list[NewsItem]:
    feed_url = RSS_URL_TEMPLATE.format(symbol=symbol)
    feed = feedparser.parse(feed_url)

    items: list[NewsItem] = []
    for entry in feed.entries[:max_items]:
        url = getattr(entry, "link", "").strip()
        if not url:
            continue

        article_text = extract_article_text(url, timeout_seconds)
        if not article_text:
            article_text = getattr(entry, "summary", "").strip()

        items.append(
            NewsItem(
                symbol=symbol,
                title=getattr(entry, "title", "").strip(),
                url=url,
                published_at=_normalize_published_at(entry),
                source=_extract_source_name(entry),
                article_text=article_text.strip(),
            )
        )

    return items


def extract_article_text(url: str, timeout_seconds: int) -> str:
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={"User-Agent": "stock-news-discord-bot/0.1"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""

    downloaded = trafilatura.extract(
        response.text,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    return (downloaded or "").strip()


def _normalize_published_at(entry: Any) -> str:
    published = getattr(entry, "published", "").strip()
    if published:
        try:
            return parsedate_to_datetime(published).isoformat()
        except (TypeError, ValueError, IndexError, OverflowError):
            return published
    return ""


def _extract_source_name(entry: Any) -> str:
    source = getattr(entry, "source", None)
    if source and getattr(source, "title", ""):
        return str(source.title).strip()
    return "Yahoo Finance RSS"
