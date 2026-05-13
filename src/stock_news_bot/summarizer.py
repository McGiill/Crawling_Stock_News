from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from stock_news_bot.fetcher import NewsItem


@dataclass(frozen=True)
class SymbolSummaryResult:
    headline: str
    summary_lines: list[str]
    sentiment: str
    reason: str


@dataclass(frozen=True)
class MarketOverviewResult:
    headline: str
    summary_lines: list[str]
    us_market: str
    kr_market: str
    exchange_rate: str
    key_driver: str
    risk_factor: str


@dataclass(frozen=True)
class SectorOverviewResult:
    headline: str
    summary_lines: list[str]
    strong_sectors: list[str]
    weak_sectors: list[str]


def summarize_symbol_news(
    *,
    api_key: str,
    model: str,
    symbol: str,
    articles: list[NewsItem],
) -> SymbolSummaryResult:
    prompt = f"""
당신은 미국 주식 뉴스 브리핑 분석가입니다.
아래 여러 개의 영어 뉴스 정보를 종합해 반드시 JSON으로만 답하세요.

요구사항:
1. 이 종목의 오늘 핵심 이슈를 한 줄 제목처럼 한국어로 정리합니다.
2. 여러 기사를 종합한 한국어 3줄 요약을 작성합니다.
3. 시장 관점에서 종합 감성 분류를 `호재`, `악재`, `중립` 중 하나로 고릅니다.
4. 감성 분류 이유를 한국어 한 문장으로 작성합니다.
5. 중복되는 내용은 합쳐서 정리하고, 잡음성 기사보다 해당 종목에 직접 영향이 큰 이슈를 우선합니다.
6. 기사 내용이 상충하거나 종목 직접 영향이 약하면 보수적으로 `중립`에 가깝게 판단합니다.

반환 JSON 스키마:
{{
  "headline": "...",
  "summary_lines": ["...", "...", "..."],
  "sentiment": "호재|악재|중립",
  "reason": "..."
}}

종목: {symbol}
기사 묶음:
{_build_article_block(articles)}
""".strip()
    parsed = _request_json(api_key=api_key, model=model, prompt=prompt)

    return SymbolSummaryResult(
        headline=_require_text(parsed, "headline"),
        summary_lines=_parse_summary_lines(parsed),
        sentiment=_parse_sentiment(parsed),
        reason=_require_text(parsed, "reason"),
    )


def summarize_market_overview(
    *,
    api_key: str,
    model: str,
    us_articles_by_symbol: dict[str, list[NewsItem]],
    kr_articles_by_symbol: dict[str, list[NewsItem]],
) -> MarketOverviewResult:
    prompt = f"""
당신은 미국/한국 증시를 함께 보는 글로벌 시장 브리핑 분석가입니다.
아래 뉴스 묶음을 읽고 반드시 JSON으로만 답하세요.

요구사항:
1. 오늘 시장 전체 흐름을 한국어 한 줄 제목으로 정리합니다.
2. 한국어 3줄 요약을 작성합니다.
3. 미국 시장 흐름을 정리할 때, 구체적인 지수(S&P 500, 나스닥 등) 변화와 주요 경제 지표를 포함하여 깊이 있게 2~3문장으로 분석합니다.
4. 한국 시장 흐름을 정리할 때, 코스피/코스닥의 유의미한 급등락 등 시장에 큰 영향을 미치는 지표 변화가 있다면 반드시 포함하여 2~3문장으로 구체적으로 분석합니다.
5. 뉴스에 나타난 원/달러 환율 동향을 파악하여 한 문장으로 정리합니다. (환율 정보는 고정으로 출력합니다)
6. 오늘 핵심 동인 1개와 주요 리스크 1개를 각각 구체적인 이유와 함께 한 문장으로 정리합니다.
7. 과장 없이 사실 중심으로 정리하고, 기사 간 충돌이 있으면 보수적으로 표현합니다.

반환 JSON 스키마:
{{
  "headline": "...",
  "summary_lines": ["...", "...", "..."],
  "us_market": "...",
  "kr_market": "...",
  "exchange_rate": "...",
  "key_driver": "...",
  "risk_factor": "..."
}}

[미국 시장 뉴스]
{_build_symbol_group_block(us_articles_by_symbol)}

[한국 시장 뉴스]
{_build_symbol_group_block(kr_articles_by_symbol)}
""".strip()
    parsed = _request_json(api_key=api_key, model=model, prompt=prompt)

    return MarketOverviewResult(
        headline=_require_text(parsed, "headline"),
        summary_lines=_parse_summary_lines(parsed),
        us_market=_require_text(parsed, "us_market"),
        kr_market=_require_text(parsed, "kr_market"),
        exchange_rate=_require_text(parsed, "exchange_rate"),
        key_driver=_require_text(parsed, "key_driver"),
        risk_factor=_require_text(parsed, "risk_factor"),
    )


def summarize_sector_overview(
    *,
    api_key: str,
    model: str,
    sector_articles_by_symbol: dict[str, list[NewsItem]],
) -> SectorOverviewResult:
    prompt = f"""
당신은 미국 시장의 섹터 로테이션을 분석하는 애널리스트입니다.
아래 섹터 관련 뉴스 묶음을 읽고 반드시 JSON으로만 답하세요.

요구사항:
1. 오늘 섹터 흐름을 한국어 한 줄 제목으로 정리합니다.
2. 한국어 3줄 요약을 작성합니다.
3. 강한 섹터 2~3개를 고르고 한국어로 간단한 이유를 붙입니다.
4. 약한 섹터 2~3개를 고르고 한국어로 간단한 이유를 붙입니다.
5. 강/약 판단은 기사 톤과 이슈 강도를 바탕으로 보수적으로 정리합니다.

반환 JSON 스키마:
{{
  "headline": "...",
  "summary_lines": ["...", "...", "..."],
  "strong_sectors": ["섹터명: 이유", "섹터명: 이유"],
  "weak_sectors": ["섹터명: 이유", "섹터명: 이유"]
}}

[섹터 뉴스]
{_build_symbol_group_block(sector_articles_by_symbol)}
""".strip()
    parsed = _request_json(api_key=api_key, model=model, prompt=prompt)

    strong_sectors = _parse_string_list(parsed, "strong_sectors")
    weak_sectors = _parse_string_list(parsed, "weak_sectors")
    if not strong_sectors:
        raise ValueError("strong_sectors must not be empty.")
    if not weak_sectors:
        raise ValueError("weak_sectors must not be empty.")

    return SectorOverviewResult(
        headline=_require_text(parsed, "headline"),
        summary_lines=_parse_summary_lines(parsed),
        strong_sectors=strong_sectors[:3],
        weak_sectors=weak_sectors[:3],
    )


def _request_json(*, api_key: str, model: str, prompt: str) -> dict[str, object]:
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    raw_text = response.output_text.strip()
    raw_json = _extract_json_object(raw_text)
    parsed = json.loads(raw_json)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object.")
    return parsed


def _parse_summary_lines(parsed: dict[str, object]) -> list[str]:
    summary_lines = parsed.get("summary_lines", [])
    if not isinstance(summary_lines, list):
        raise ValueError("summary_lines must be a list.")

    normalized_lines = [str(line).strip() for line in summary_lines if str(line).strip()][:3]
    if len(normalized_lines) != 3:
        raise ValueError("summary_lines must contain exactly 3 non-empty lines.")
    return normalized_lines


def _parse_sentiment(parsed: dict[str, object]) -> str:
    sentiment = str(parsed.get("sentiment", "")).strip()
    if sentiment not in {"호재", "악재", "중립"}:
        raise ValueError("sentiment must be one of 호재, 악재, 중립.")
    return sentiment


def _parse_string_list(parsed: dict[str, object], key: str) -> list[str]:
    value = parsed.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list.")
    return [str(item).strip() for item in value if str(item).strip()]


def _require_text(parsed: dict[str, object], key: str) -> str:
    value = str(parsed.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} must not be empty.")
    return value


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        return match.group(0)

    raise ValueError("Could not find a JSON object in model output.")


def _build_symbol_group_block(articles_by_symbol: dict[str, list[NewsItem]]) -> str:
    chunks: list[str] = []
    for symbol, articles in articles_by_symbol.items():
        if not articles:
            continue
        chunks.append(f"[{symbol}]\n{_build_article_block(articles)}")
    return "\n\n".join(chunks) or "기사 없음"


def _build_article_block(articles: list[NewsItem]) -> str:
    chunks: list[str] = []
    for index, article in enumerate(articles, start=1):
        text = article.article_text[:3500]
        chunks.append(
            (
                f"[기사 {index}]\n"
                f"제목: {article.title}\n"
                f"출처: {article.source}\n"
                f"발행시각: {article.published_at or 'unknown'}\n"
                f"링크: {article.url}\n"
                f"본문:\n{text}"
            )
        )
    return "\n\n".join(chunks)
