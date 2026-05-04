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


def summarize_symbol_news(
    *,
    api_key: str,
    model: str,
    symbol: str,
    articles: list[NewsItem],
) -> SymbolSummaryResult:
    client = OpenAI(api_key=api_key)
    article_block = _build_article_block(articles)

    prompt = f"""
당신은 미국 주식 뉴스 브리핑 분석가입니다.
아래 여러 개의 영어 뉴스 정보를 종합해 반드시 JSON으로만 답하세요.

요구사항:
1. 이 종목의 오늘 핵심 이슈를 한 줄 제목처럼 한국어로 정리합니다.
2. 여러 기사를 종합한 한국어 3줄 요약을 작성합니다.
3. 시장 관점에서 종합 감성 분류를 `호재`, `악재`, `중립` 중 하나로 고릅니다.
4. 감성 분류 이유를 한국어 한 문장으로 작성합니다.
5. 중복되는 내용은 합쳐서 정리하고, 잡음성 기사나 주변 기사보다 해당 종목에 직접 영향이 큰 이슈를 우선합니다.
6. 과장 없이 사실 중심으로 씁니다.
7. 기사 내용이 상충하거나 종목 직접 영향이 약하면 보수적으로 `중립`에 가깝게 판단합니다.

반환 JSON 스키마:
{{
  "headline": "...",
  "summary_lines": ["...", "...", "..."],
  "sentiment": "호재|악재|중립",
  "reason": "..."
}}

종목: {symbol}
기사 묶음:
{article_block}
""".strip()

    response = client.responses.create(
        model=model,
        input=prompt,
    )

    raw_text = response.output_text.strip()
    raw_json = _extract_json_object(raw_text)
    parsed = json.loads(raw_json)

    headline = str(parsed.get("headline", "")).strip()
    if not headline:
        raise ValueError("headline must not be empty.")

    summary_lines = parsed.get("summary_lines", [])
    if not isinstance(summary_lines, list):
        raise ValueError("summary_lines must be a list.")

    normalized_lines = [str(line).strip() for line in summary_lines if str(line).strip()][:3]
    if len(normalized_lines) != 3:
        raise ValueError("summary_lines must contain exactly 3 non-empty lines.")

    sentiment = str(parsed.get("sentiment", "")).strip()
    reason = str(parsed.get("reason", "")).strip()

    if sentiment not in {"호재", "악재", "중립"}:
        raise ValueError("sentiment must be one of 호재, 악재, 중립.")
    if not reason:
        raise ValueError("reason must not be empty.")

    return SymbolSummaryResult(
        headline=headline,
        summary_lines=normalized_lines,
        sentiment=sentiment,
        reason=reason,
    )


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        return match.group(0)

    raise ValueError("Could not find a JSON object in model output.")


def _build_article_block(articles: list[NewsItem]) -> str:
    chunks: list[str] = []
    for index, article in enumerate(articles, start=1):
        text = article.article_text[:4000]
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
