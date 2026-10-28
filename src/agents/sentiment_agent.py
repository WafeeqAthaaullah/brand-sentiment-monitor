import json
import logging
from typing import Optional
from openai import OpenAI

from config.settings import settings
from src.agents.schemas import SentimentAnalysis

logger = logging.getLogger(__name__)

FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
]
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def get_groq_client() -> Optional[OpenAI]:
    """Return configured OpenAI client for Groq or None if API key is not set."""
    api_key = settings.GROQ_API_KEY
    if not api_key or not api_key.strip() or api_key == "your_groq_api_key_here":
        return None
    return OpenAI(base_url=GROQ_BASE_URL, api_key=api_key.strip())


def analyze_post(content: str) -> SentimentAnalysis:
    """Analyze brand post content for sentiment, category, severity, and summary.

    Args:
        content: Text content of the social or web mention.

    Returns:
        Validated SentimentAnalysis Pydantic model.
    """
    client = get_groq_client()

    if not client:
        print("WARNING: GROQ_API_KEY is not configured or missing. Returning default neutral fallback.")
        return SentimentAnalysis(
            sentiment="Neutral",
            sentiment_score=0.0,
            category="General PR",
            severity_rating=1,
            summary="Groq API key not provided; returning default neutral fallback.",
        )

    system_prompt = (
        "You are an expert AI brand sentiment analyst and crisis detection agent.\n"
        "Analyze the provided post content and return a strict JSON object with these exact keys:\n"
        "- sentiment: One of 'Positive', 'Neutral', 'Negative'\n"
        "- sentiment_score: Float between -1.0 (most negative) and 1.0 (most positive)\n"
        "- category: One of 'Product Quality', 'Customer Service', 'Outage/Bug', 'Pricing', 'General PR'\n"
        "- severity_rating: Integer from 1 (routine/trivial) to 10 (critical emergency/severe crisis)\n"
        "- summary: A concise one-sentence factual summary explaining the assessment."
    )

    models_to_try = [settings.GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != settings.GROQ_MODEL]

    for model_name in models_to_try:
        try:
            # Try structured parsing via parse endpoint
            completion = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Post Content:\n{content}"},
                ],
                response_format=SentimentAnalysis,
                temperature=0.1,
            )
            parsed = completion.choices[0].message.parsed
            if parsed:
                return parsed

        except Exception as parse_error:
            logger.debug("Structured parse failed with %s (%s). Falling back to JSON mode.", model_name, parse_error)

        # Fallback to standard JSON mode
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Post Content:\n{content}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw_json_str = response.choices[0].message.content or "{}"
            data = json.loads(raw_json_str)
            return SentimentAnalysis.model_validate(data)

        except Exception as e:
            logger.warning("Groq model %s failed: %s", model_name, e)
            continue

    print("WARNING: All Groq candidate models failed. Returning default fallback analysis.")
    return SentimentAnalysis(
        sentiment="Neutral",
        sentiment_score=0.0,
        category="General PR",
        severity_rating=1,
        summary="Analysis could not be completed with available Groq models.",
    )


if __name__ == "__main__":
    test_content = "The platform update completely deleted our team workspace database!"
    print(f"Analyzing test post:\n'{test_content}'\n")

    result = analyze_post(test_content)
    print("--- Sentiment Analysis Result ---")
    print(f"Sentiment: {result.sentiment}")
    print(f"Score: {result.sentiment_score}")
    print(f"Category: {result.category}")
    print(f"Severity: {result.severity_rating}/10")
    print(f"Summary: {result.summary}")
    print("\nPydantic dict dump:")
    print(result.model_dump())
