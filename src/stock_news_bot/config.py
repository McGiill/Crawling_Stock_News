from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    discord_webhook_url: str
    watchlist: list[str]
    us_market_symbols: list[str]
    kr_market_symbols: list[str]
    sector_symbols: list[str]
    max_articles_per_symbol: int
    max_market_articles_per_symbol: int
    max_sector_articles_per_symbol: int
    request_timeout_seconds: int
    sent_articles_path: str


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _parse_symbols(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default).strip()
    if not raw:
        return []
    return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]


def load_settings() -> Settings:
    load_dotenv()

    watchlist = _parse_symbols("WATCHLIST")
    if not watchlist:
        raise ValueError("WATCHLIST must include at least one symbol.")

    discord_webhook_url = _require_env("DISCORD_WEBHOOK_URL")
    if discord_webhook_url.endswith("/...") or discord_webhook_url == "https://discord.com/api/webhooks/...":
        raise ValueError(
            "DISCORD_WEBHOOK_URL is still a placeholder. Replace it with the full Discord webhook URL."
        )

    return Settings(
        openai_api_key=_require_env("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini",
        discord_webhook_url=discord_webhook_url,
        watchlist=watchlist,
        us_market_symbols=_parse_symbols("US_MARKET_SYMBOLS", "SPY,QQQ,DIA,IWM,^VIX,^TNX"),
        kr_market_symbols=_parse_symbols("KR_MARKET_SYMBOLS", "EWY,^KS11,^KQ11,USDKRW=X"),
        sector_symbols=_parse_symbols(
            "SECTOR_SYMBOLS",
            "XLK,XLE,XLF,XLV,XLY,XLI,XLP,XLB,XLU,VNQ,SMH",
        ),
        max_articles_per_symbol=int(os.getenv("MAX_ARTICLES_PER_SYMBOL", "5")),
        max_market_articles_per_symbol=int(os.getenv("MAX_MARKET_ARTICLES_PER_SYMBOL", "3")),
        max_sector_articles_per_symbol=int(os.getenv("MAX_SECTOR_ARTICLES_PER_SYMBOL", "2")),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
        sent_articles_path=os.getenv("SENT_ARTICLES_PATH", "data/sent_articles.json"),
    )
