"""
Pydantic models for API requests and responses.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    CUSTOM = "custom"


class DifferenceType(str, Enum):
    """Types of differences found in comparison."""
    CONTENT_CHANGE = "CONTENT_CHANGE"
    FORMATTING = "FORMATTING"
    ADDITION = "ADDITION"
    DELETION = "DELETION"


class SimilarityRating(str, Enum):
    """Similarity ratings for text comparison."""
    IDENTICAL = "IDENTICAL"
    VERY_SIMILAR = "VERY_SIMILAR"
    SIMILAR = "SIMILAR"
    DIFFERENT = "DIFFERENT"
    VERY_DIFFERENT = "VERY_DIFFERENT"


class BoundingBox(BaseModel):
    """Bounding box coordinates for marking differences."""
    x: float
    y: float
    width: float
    height: float


class LLMConfig(BaseModel):
    """LLM configuration from UI."""
    provider: LLMProvider
    api_key: str = Field(..., min_length=1, description="API key for the LLM provider")
    model: str = Field(..., min_length=1, description="Model name (e.g., gpt-4, claude-3-sonnet-20240229)")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="Temperature for LLM responses")
    custom_endpoint: Optional[str] = Field(default=None, description="Custom endpoint URL for custom providers")
    max_tokens: int = Field(default=4000, gt=0, description="Maximum tokens for response")


class ComparisonRequest(BaseModel):
    """Request model for PDF comparison (multipart form data)."""
    llm_config: LLMConfig


class ComparisonResponse(BaseModel):
    """Response model for comparison job creation."""
    job_id: str
    status: str = "processing"
    message: str = "Comparison started"


class JobStatus(BaseModel):
    """Job status information."""
    job_id: str
    status: str  # processing, completed, failed
    progress: int = Field(default=0, ge=0, le=100)
    current_step: Optional[str] = None
    error: Optional[str] = None


class DifferenceResult(BaseModel):
    """Individual difference found during comparison."""
    page: int
    type: DifferenceType
    source_text: str
    copy_text: str
    reasoning: str
    bbox: Optional[BoundingBox] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class PageAnalysis(BaseModel):
    """Analysis result for a single page pair."""
    page_number: int
    similarity_rating: SimilarityRating
    overall_reasoning: str
    differences: List[DifferenceResult]
    has_differences: bool


class ComparisonSummary(BaseModel):
    """Summary of the comparison results."""
    total_pages: int
    pages_with_differences: int
    similarity_score: float = Field(ge=0.0, le=100.0)
    llm_used: str  # e.g., "OpenAI GPT-4"
    methodology: str
    comparison_date: str


class ComparisonResult(BaseModel):
    """Complete comparison result."""
    job_id: str
    output_pdf_url: str
    summary: ComparisonSummary
    differences: List[DifferenceResult]
    page_analyses: Optional[List[PageAnalysis]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    job_id: Optional[str] = None
