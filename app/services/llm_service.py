"""
LLM service with provider abstraction for OpenAI, Anthropic, Gemini, and custom endpoints.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import json
import logging
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai
import httpx

from app.models.schemas import LLMConfig, LLMProvider, DifferenceType, SimilarityRating

logger = logging.getLogger(__name__)


class LLMAnalysisResult:
    """Container for LLM analysis results."""
    def __init__(self, similarity_rating: str, overall_reasoning: str, differences: List[Dict[str, Any]]):
        self.similarity_rating = similarity_rating
        self.overall_reasoning = overall_reasoning
        self.differences = differences


class LLMProviderBase(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def analyze_text(self, source_text: str, copy_text: str, page_num: int) -> LLMAnalysisResult:
        """
        Analyze differences between source and copy text.

        Args:
            source_text: Text from source PDF
            copy_text: Text from copy PDF
            page_num: Page number being analyzed

        Returns:
            LLMAnalysisResult with similarities and differences
        """
        pass

    def _create_prompt(self, source_text: str, copy_text: str, page_num: int) -> str:
        """Create the comparison prompt."""
        return f"""Compare these text segments from page {page_num + 1}:

SOURCE:
{source_text}

COPY:
{copy_text}

Tasks:
1. List all textual differences with exact quotes
2. Categorize each difference: [CONTENT_CHANGE | FORMATTING | ADDITION | DELETION]
3. Explain WHY each is considered a difference
4. Rate overall similarity: [IDENTICAL | VERY_SIMILAR | SIMILAR | DIFFERENT | VERY_DIFFERENT]
5. Provide reasoning for similarity rating

Return your response as JSON with this structure:
{{
  "similarity_rating": "SIMILAR",
  "overall_reasoning": "explanation of overall similarity",
  "differences": [
    {{
      "type": "CONTENT_CHANGE",
      "source": "exact quote from source",
      "copy": "exact quote from copy",
      "reasoning": "explanation of why this differs"
    }}
  ]
}}

If the texts are identical, return an empty differences array and similarity_rating as "IDENTICAL"."""

    def _parse_response(self, response_text: str) -> LLMAnalysisResult:
        """Parse LLM response into structured format."""
        try:
            # Try to extract JSON from response
            # Some models wrap JSON in markdown code blocks
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            data = json.loads(response_text)

            return LLMAnalysisResult(
                similarity_rating=data.get("similarity_rating", "SIMILAR"),
                overall_reasoning=data.get("overall_reasoning", ""),
                differences=data.get("differences", [])
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            # Return a default result if parsing fails
            return LLMAnalysisResult(
                similarity_rating="SIMILAR",
                overall_reasoning="Unable to parse detailed analysis",
                differences=[]
            )


class OpenAIProvider(LLMProviderBase):
    """OpenAI LLM provider implementation."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = OpenAI(api_key=config.api_key)

    def analyze_text(self, source_text: str, copy_text: str, page_num: int) -> LLMAnalysisResult:
        """Analyze text using OpenAI API."""
        prompt = self._create_prompt(source_text, copy_text, page_num)

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise document comparison assistant. Analyze text segments and provide detailed, objective assessments of similarities and differences. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"}  # Enforce JSON response
            )

            response_text = response.choices[0].message.content
            logger.debug(f"OpenAI response for page {page_num}: {response_text[:200]}...")

            return self._parse_response(response_text)

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class AnthropicProvider(LLMProviderBase):
    """Anthropic (Claude) LLM provider implementation."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = Anthropic(api_key=config.api_key)

    def analyze_text(self, source_text: str, copy_text: str, page_num: int) -> LLMAnalysisResult:
        """Analyze text using Anthropic API."""
        prompt = self._create_prompt(source_text, copy_text, page_num)

        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system="You are a precise document comparison assistant. Analyze text segments and provide detailed, objective assessments of similarities and differences. Always respond with valid JSON.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = response.content[0].text
            logger.debug(f"Anthropic response for page {page_num}: {response_text[:200]}...")

            return self._parse_response(response_text)

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


class GeminiProvider(LLMProviderBase):
    """Google Gemini LLM provider implementation with retry logic."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        genai.configure(api_key=config.api_key)
        self.model = genai.GenerativeModel(config.model)

    def analyze_text(self, source_text: str, copy_text: str, page_num: int) -> LLMAnalysisResult:
        """Analyze text using Google Gemini API with retry logic."""
        prompt = self._create_prompt(source_text, copy_text, page_num)

        # Retry configuration
        max_retries = 3
        base_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                # Configure generation settings
                generation_config = {
                    "temperature": self.config.temperature,
                    "max_output_tokens": self.config.max_tokens,
                }

                # Create the full prompt with system instruction
                full_prompt = (
                    "You are a precise document comparison assistant. "
                    "Analyze text segments and provide detailed, objective assessments of similarities and differences. "
                    "Always respond with valid JSON.\n\n" + prompt
                )

                response = self.model.generate_content(
                    full_prompt,
                    generation_config=generation_config
                )

                response_text = response.text
                logger.debug(f"Gemini response for page {page_num}: {response_text[:200]}...")

                return self._parse_response(response_text)

            except Exception as e:
                error_str = str(e)

                # Check if it's a quota/rate limit error
                if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                    if attempt < max_retries - 1:
                        import time
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Gemini rate limit hit for page {page_num}. Retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Gemini quota exceeded after {max_retries} retries for page {page_num}")
                        # Return a fallback result instead of crashing
                        return LLMAnalysisResult(
                            similarity_rating="SIMILAR",
                            overall_reasoning="Unable to analyze due to API quota limits. Please upgrade to a paid API key or try again later.",
                            differences=[]
                        )
                else:
                    logger.error(f"Gemini API error: {e}")
                    raise


class CustomProvider(LLMProviderBase):
    """Custom LLM provider for generic API endpoints."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not config.custom_endpoint:
            raise ValueError("Custom endpoint URL is required for custom provider")
        self.endpoint = config.custom_endpoint

    def analyze_text(self, source_text: str, copy_text: str, page_num: int) -> LLMAnalysisResult:
        """Analyze text using custom API endpoint."""
        prompt = self._create_prompt(source_text, copy_text, page_num)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise document comparison assistant. Analyze text segments and provide detailed, objective assessments of similarities and differences. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()

                data = response.json()

                # Try to extract response text from common response formats
                response_text = None
                if "choices" in data and len(data["choices"]) > 0:
                    response_text = data["choices"][0].get("message", {}).get("content")
                elif "content" in data:
                    response_text = data["content"]
                elif "response" in data:
                    response_text = data["response"]

                if not response_text:
                    logger.error(f"Unable to extract response from custom API: {data}")
                    raise ValueError("Unable to extract response from custom API")

                logger.debug(f"Custom API response for page {page_num}: {response_text[:200]}...")

                return self._parse_response(response_text)

        except httpx.HTTPError as e:
            logger.error(f"Custom API HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Custom API error: {e}")
            raise


def get_llm_provider(config: LLMConfig) -> LLMProviderBase:
    """
    Factory function to get the appropriate LLM provider.

    Args:
        config: LLM configuration from UI

    Returns:
        Appropriate LLM provider instance

    Raises:
        ValueError: If provider is not supported
    """
    if config.provider == LLMProvider.OPENAI:
        return OpenAIProvider(config)
    elif config.provider == LLMProvider.ANTHROPIC:
        return AnthropicProvider(config)
    elif config.provider == LLMProvider.GEMINI:
        return GeminiProvider(config)
    elif config.provider == LLMProvider.CUSTOM:
        return CustomProvider(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")
