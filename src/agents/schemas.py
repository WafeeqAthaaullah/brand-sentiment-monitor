from typing import Literal
from pydantic import BaseModel, Field

SentimentType = Literal["Positive", "Neutral", "Negative"]


class SentimentAnalysis(BaseModel):
    """Structured output schema for LLM-based sentiment and crisis analysis."""

    sentiment: SentimentType = Field(
        ...,
        description="Sentiment classification of the mention.",
    )
    sentiment_score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Normalized sentiment score ranging from -1.0 (most negative) to 1.0 (most positive).",
    )
    category: str = Field(
        ...,
        description="Primary operational category in Title Case, 2-3 words max (e.g., 'Battery Degradation', 'UI Glitch', 'Customer Service')",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Top 2-4 granular topic tags",
    )
    key_entities: list[str] = Field(
        default_factory=list,
        description="Key brands, products, competitors, or people mentioned",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Top 3-5 operational keywords",
    )
    severity_rating: int = Field(
        ...,
        ge=1,
        le=10,
        description="Severity rating from 1 (minor/routine) to 10 (critical brand emergency).",
    )
    summary: str = Field(
        ...,
        description="Concise one-sentence summary or justification of the sentiment assessment.",
    )
