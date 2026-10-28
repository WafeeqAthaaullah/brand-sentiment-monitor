import json
import logging
from typing import Any
from config.settings import settings
from src.agents.sentiment_agent import FALLBACK_MODELS, get_groq_client

logger = logging.getLogger(__name__)


def answer_telemetry_question(question: str, records: list[dict[str, Any]]) -> str:
    """Answer a user query accurately based ONLY on the provided telemetry records.

    Args:
        question: User query text.
        records: List of relevant database record dicts (title, sentiment, severity, summary, content, etc.).

    Returns:
        Structured, factual analyst response.
    """
    if not records:
        return "No telemetry records are currently available in the database to answer this question. Please run the ingestion pipeline to collect data."

    client = get_groq_client()
    if not client:
        return "Groq client is not configured. Please ensure GROQ_API_KEY is configured in your environment."

    # Format telemetry records concisely to fit within prompt context
    telemetry_snippets: list[str] = []
    for idx, r in enumerate(records[:30], start=1):
        content_preview = str(r.get("content", ""))[:250].replace("\n", " ")
        snippet = (
            f"Record #{idx} | Platform: {r.get('platform')} | Date: {r.get('timestamp')} | "
            f"Sentiment: {r.get('sentiment')} (Score: {r.get('sentiment_score')}) | "
            f"Category: {r.get('category')} | Severity: {r.get('severity_rating')}/10 | "
            f"Summary: {r.get('summary')} | Key Entities: {r.get('key_entities', '[]')} | "
            f"Keywords: {r.get('keywords', '[]')} | Content: {content_preview}"
        )
        telemetry_snippets.append(snippet)

    context_str = "\n".join(telemetry_snippets)

    system_prompt = (
        "You are an expert brand intelligence analyst and PR strategist.\n"
        "Answer the user's question accurately and objectively based ONLY on the provided telemetry records below.\n"
        "If the records do not contain enough information to fully address the question, clearly state the limitation.\n"
        "Provide concise, actionable insights using structured Markdown sections and bold bullet points (e.g., '### Top Complaint Themes', '**1. Software Bugs (12 records):** Users report...').\n"
        "DO NOT output raw Markdown pipe tables (`|---|`), as they break rendering."
    )

    user_prompt = (
        f"Telemetry Ingested Records ({len(records)} total records provided):\n"
        f"{context_str}\n\n"
        f"User Question: {question}"
    )

    models_to_try = [settings.GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != settings.GROQ_MODEL]

    for model_name in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2048,
            )
            content = response.choices[0].message.content
            if content:
                return content.strip()
        except Exception as e:
            logger.warning("Groq model %s failed for Q&A: %s", model_name, e)
            continue

    return "Unable to generate an answer at this time due to an LLM provider error. Please try again."

