from typing import Literal
from pydantic import BaseModel, Field

SentimentType = Literal["Positive", "Neutral", "Negative"]
CategoryType = Literal[
    "Product Quality",
    "Customer Service",
    "Outage/Bug",
    "Pricing",
    "General PR",
]


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
    category: CategoryType = Field(
        ...,
        description="Category classification indicating the core focus/issue of the post.",
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

