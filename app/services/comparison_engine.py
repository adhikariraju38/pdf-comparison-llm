"""
Core comparison engine that orchestrates the PDF comparison workflow.
"""
import difflib
from typing import List, Dict, Tuple, Any
import logging
from pathlib import Path

from app.models.schemas import (
    LLMConfig, DifferenceResult, DifferenceType,
    PageAnalysis, SimilarityRating, BoundingBox, ComparisonSummary
)
from app.services.pdf_extractor import PDFExtractor, PDFBlock, extract_all_pages_blocks
from app.services.llm_service import get_llm_provider, LLMAnalysisResult

logger = logging.getLogger(__name__)


class ComparisonEngine:
    """Core engine for comparing two PDFs."""

    def __init__(self, source_pdf_path: str, copy_pdf_path: str, llm_config: LLMConfig):
        """
        Initialize the comparison engine.

        Args:
            source_pdf_path: Path to source PDF
            copy_pdf_path: Path to copy PDF
            llm_config: LLM configuration from UI
        """
        self.source_pdf_path = source_pdf_path
        self.copy_pdf_path = copy_pdf_path
        self.llm_config = llm_config
        self.llm_provider = get_llm_provider(llm_config)

    def compare(self, progress_callback=None) -> Tuple[List[PageAnalysis], ComparisonSummary]:
        """
        Perform complete comparison of two PDFs.

        Args:
            progress_callback: Optional callback function(step: str, progress: int)

        Returns:
            Tuple of (page_analyses, summary)
        """
        logger.info(f"Starting comparison: {self.source_pdf_path} vs {self.copy_pdf_path}")

        if progress_callback:
            progress_callback("Extracting source PDF...", 10)

        # Extract text blocks from both PDFs
        source_blocks = extract_all_pages_blocks(self.source_pdf_path)

        if progress_callback:
            progress_callback("Extracting copy PDF...", 20)

        copy_blocks = extract_all_pages_blocks(self.copy_pdf_path)

        # Align pages
        max_pages = max(len(source_blocks), len(copy_blocks))
        page_analyses = []

        logger.info(f"Comparing {max_pages} pages...")

        for page_num in range(max_pages):
            if progress_callback:
                progress_pct = 20 + int((page_num / max_pages) * 60)
                progress_callback(f"Analyzing page {page_num + 1} of {max_pages}...", progress_pct)

            analysis = self._compare_page(page_num, source_blocks, copy_blocks)
            page_analyses.append(analysis)

        if progress_callback:
            progress_callback("Generating summary...", 90)

        # Generate summary
        summary = self._generate_summary(page_analyses)

        logger.info(f"Comparison complete: {summary.pages_with_differences}/{summary.total_pages} pages with differences")

        return page_analyses, summary

    def _compare_page(
        self,
        page_num: int,
        source_blocks: List[List[PDFBlock]],
        copy_blocks: List[List[PDFBlock]]
    ) -> PageAnalysis:
        """
        Compare a single page pair.

        Args:
            page_num: Page number (0-indexed)
            source_blocks: All blocks from source PDF
            copy_blocks: All blocks from copy PDF

        Returns:
            PageAnalysis object
        """
        # Get blocks for this page
        source_page_blocks = source_blocks[page_num] if page_num < len(source_blocks) else []
        copy_page_blocks = copy_blocks[page_num] if page_num < len(copy_blocks) else []

        # Extract full text from blocks
        source_text = "\n".join([block.text for block in source_page_blocks])
        copy_text = "\n".join([block.text for block in copy_page_blocks])

        # Quick check for identical pages
        if source_text == copy_text:
            logger.debug(f"Page {page_num + 1}: Identical")
            return PageAnalysis(
                page_number=page_num + 1,
                similarity_rating=SimilarityRating.IDENTICAL,
                overall_reasoning="Pages are identical",
                differences=[],
                has_differences=False
            )

        # Use difflib for preliminary diff detection
        preliminary_diffs = self._get_preliminary_diffs(source_text, copy_text)

        # If no preliminary differences, pages might still be very similar
        if not preliminary_diffs:
            logger.debug(f"Page {page_num + 1}: Very similar (no major diffs)")
            return PageAnalysis(
                page_number=page_num + 1,
                similarity_rating=SimilarityRating.VERY_SIMILAR,
                overall_reasoning="Pages are very similar with only minor differences",
                differences=[],
                has_differences=False
            )

        # Use LLM for detailed analysis
        try:
            llm_result = self.llm_provider.analyze_text(source_text, copy_text, page_num)

            # Convert LLM results to DifferenceResult objects
            differences = []
            for diff_dict in llm_result.differences:
                # Try to find bounding box for this difference
                bbox = self._find_difference_bbox(
                    diff_dict.get("source", ""),
                    diff_dict.get("copy", ""),
                    source_page_blocks,
                    copy_page_blocks
                )

                difference = DifferenceResult(
                    page=page_num + 1,
                    type=self._parse_difference_type(diff_dict.get("type", "CONTENT_CHANGE")),
                    source_text=diff_dict.get("source", ""),
                    copy_text=diff_dict.get("copy", ""),
                    reasoning=diff_dict.get("reasoning", ""),
                    bbox=bbox
                )
                differences.append(difference)

            # Parse similarity rating
            similarity = self._parse_similarity_rating(llm_result.similarity_rating)

            logger.debug(f"Page {page_num + 1}: {similarity.value}, {len(differences)} differences")

            return PageAnalysis(
                page_number=page_num + 1,
                similarity_rating=similarity,
                overall_reasoning=llm_result.overall_reasoning,
                differences=differences,
                has_differences=len(differences) > 0
            )

        except Exception as e:
            logger.error(f"Error analyzing page {page_num + 1}: {e}")
            # Return a fallback analysis
            return PageAnalysis(
                page_number=page_num + 1,
                similarity_rating=SimilarityRating.SIMILAR,
                overall_reasoning=f"Error during analysis: {str(e)}",
                differences=[],
                has_differences=True
            )

    def _get_preliminary_diffs(self, text1: str, text2: str) -> List[str]:
        """Use difflib to get preliminary differences."""
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()

        differ = difflib.Differ()
        diffs = list(differ.compare(lines1, lines2))

        # Filter for actual differences (lines starting with + or -)
        significant_diffs = [line for line in diffs if line.startswith('+ ') or line.startswith('- ')]

        return significant_diffs

    def _find_difference_bbox(
        self,
        source_snippet: str,
        copy_snippet: str,
        source_blocks: List[PDFBlock],
        copy_blocks: List[PDFBlock]
    ) -> BoundingBox:
        """
        Find bounding box for a difference.

        Args:
            source_snippet: Text snippet from source
            copy_snippet: Text snippet from copy
            source_blocks: Blocks from source page
            copy_blocks: Blocks from copy page

        Returns:
            BoundingBox or None
        """
        # Search for the snippet in blocks
        for block in source_blocks:
            if source_snippet in block.text or block.text in source_snippet:
                return BoundingBox(
                    x=block.bbox[0],
                    y=block.bbox[1],
                    width=block.bbox[2] - block.bbox[0],
                    height=block.bbox[3] - block.bbox[1]
                )

        # If not found in source, try copy
        for block in copy_blocks:
            if copy_snippet in block.text or block.text in copy_snippet:
                return BoundingBox(
                    x=block.bbox[0],
                    y=block.bbox[1],
                    width=block.bbox[2] - block.bbox[0],
                    height=block.bbox[3] - block.bbox[1]
                )

        # Return a default bounding box if not found
        return BoundingBox(x=0, y=0, width=100, height=20)

    def _parse_difference_type(self, type_str: str) -> DifferenceType:
        """Parse difference type string to enum."""
        try:
            return DifferenceType(type_str)
        except ValueError:
            return DifferenceType.CONTENT_CHANGE

    def _parse_similarity_rating(self, rating_str: str) -> SimilarityRating:
        """Parse similarity rating string to enum."""
        try:
            return SimilarityRating(rating_str)
        except ValueError:
            return SimilarityRating.SIMILAR

    def _generate_summary(self, page_analyses: List[PageAnalysis]) -> ComparisonSummary:
        """
        Generate summary statistics from page analyses.

        Args:
            page_analyses: List of page analysis results

        Returns:
            ComparisonSummary object
        """
        total_pages = len(page_analyses)
        pages_with_differences = sum(1 for analysis in page_analyses if analysis.has_differences)

        # Calculate similarity score (0-100)
        similarity_scores = {
            SimilarityRating.IDENTICAL: 100,
            SimilarityRating.VERY_SIMILAR: 90,
            SimilarityRating.SIMILAR: 70,
            SimilarityRating.DIFFERENT: 40,
            SimilarityRating.VERY_DIFFERENT: 10
        }

        total_score = sum(similarity_scores.get(analysis.similarity_rating, 70) for analysis in page_analyses)
        avg_similarity = total_score / total_pages if total_pages > 0 else 0

        # Get LLM info
        llm_used = f"{self.llm_config.provider.value.title()} {self.llm_config.model}"

        # Get current timestamp
        from datetime import datetime
        comparison_date = datetime.now().isoformat()

        methodology = (
            f"Hybrid text extraction and LLM analysis using {llm_used}. "
            "Text blocks were extracted from both PDFs, compared using preliminary diff analysis, "
            "and then analyzed by the LLM for semantic differences. "
            "Differences are marked with red boxes on the output PDF."
        )

        return ComparisonSummary(
            total_pages=total_pages,
            pages_with_differences=pages_with_differences,
            similarity_score=round(avg_similarity, 2),
            llm_used=llm_used,
            methodology=methodology,
            comparison_date=comparison_date
        )
