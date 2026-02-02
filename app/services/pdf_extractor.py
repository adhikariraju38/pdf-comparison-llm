"""
PDF extraction service using PyMuPDF (fitz) for text and structure extraction.
"""
import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Any
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class PDFMetadata:
    """PDF metadata container."""
    def __init__(self, page_count: int, dimensions: List[Tuple[float, float]]):
        self.page_count = page_count
        self.dimensions = dimensions  # List of (width, height) for each page


class PDFBlock:
    """Represents a text block with position information."""
    def __init__(self, text: str, bbox: Tuple[float, float, float, float], page: int):
        self.text = text
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.page = page

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "bbox": {"x": self.bbox[0], "y": self.bbox[1], "width": self.bbox[2] - self.bbox[0], "height": self.bbox[3] - self.bbox[1]},
            "page": self.page
        }


class PDFExtractor:
    """Service for extracting content from PDF files."""

    def __init__(self, pdf_path: str, dpi: int = 300):
        """
        Initialize the PDF extractor.

        Args:
            pdf_path: Path to the PDF file
            dpi: Resolution for page rendering (default: 300)
        """
        self.pdf_path = pdf_path
        self.dpi = dpi
        self.doc = None

    def __enter__(self):
        """Context manager entry."""
        self.doc = fitz.open(self.pdf_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.doc:
            self.doc.close()

    def get_pdf_metadata(self) -> PDFMetadata:
        """
        Extract PDF metadata.

        Returns:
            PDFMetadata object with page count and dimensions
        """
        if not self.doc:
            raise ValueError("PDF document not opened. Use context manager.")

        page_count = len(self.doc)
        dimensions = []

        for page_num in range(page_count):
            page = self.doc[page_num]
            rect = page.rect
            dimensions.append((rect.width, rect.height))

        logger.info(f"PDF metadata: {page_count} pages, dimensions: {dimensions}")
        return PDFMetadata(page_count, dimensions)

    def extract_text_with_positions(self, page_num: int) -> List[PDFBlock]:
        """
        Extract text with bounding box positions from a specific page.

        Args:
            page_num: Page number (0-indexed)

        Returns:
            List of PDFBlock objects containing text and positions
        """
        if not self.doc:
            raise ValueError("PDF document not opened. Use context manager.")

        if page_num >= len(self.doc) or page_num < 0:
            raise ValueError(f"Page number {page_num} out of range")

        page = self.doc[page_num]
        blocks = []

        # Extract text blocks with positions
        text_blocks = page.get_text("dict")["blocks"]

        for block in text_blocks:
            if "lines" in block:  # Text block
                block_text_lines = []
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        line_text += span["text"]
                    block_text_lines.append(line_text)

                block_text = "\n".join(block_text_lines)
                bbox = block["bbox"]  # (x0, y0, x1, y1)

                if block_text.strip():  # Only add non-empty blocks
                    blocks.append(PDFBlock(block_text.strip(), bbox, page_num))

        logger.debug(f"Extracted {len(blocks)} text blocks from page {page_num}")
        return blocks

    def extract_page_structure(self, page_num: int) -> Dict[str, Any]:
        """
        Extract detailed structure information from a page.

        Args:
            page_num: Page number (0-indexed)

        Returns:
            Dictionary containing blocks, lines, and spans
        """
        if not self.doc:
            raise ValueError("PDF document not opened. Use context manager.")

        if page_num >= len(self.doc) or page_num < 0:
            raise ValueError(f"Page number {page_num} out of range")

        page = self.doc[page_num]
        structure = page.get_text("dict")

        return {
            "width": structure["width"],
            "height": structure["height"],
            "blocks": structure.get("blocks", [])
        }

    def extract_full_text(self, page_num: int) -> str:
        """
        Extract all text from a page as a single string.

        Args:
            page_num: Page number (0-indexed)

        Returns:
            Full text content of the page
        """
        if not self.doc:
            raise ValueError("PDF document not opened. Use context manager.")

        if page_num >= len(self.doc) or page_num < 0:
            raise ValueError(f"Page number {page_num} out of range")

        page = self.doc[page_num]
        text = page.get_text("text")

        logger.debug(f"Extracted {len(text)} characters from page {page_num}")
        return text

    def render_page_to_image(self, page_num: int, output_path: str = None) -> Image.Image:
        """
        Render a PDF page to an image.

        Args:
            page_num: Page number (0-indexed)
            output_path: Optional path to save the image

        Returns:
            PIL Image object
        """
        if not self.doc:
            raise ValueError("PDF document not opened. Use context manager.")

        if page_num >= len(self.doc) or page_num < 0:
            raise ValueError(f"Page number {page_num} out of range")

        page = self.doc[page_num]

        # Calculate zoom factor based on desired DPI
        # Default PDF DPI is 72, so zoom = desired_dpi / 72
        zoom = self.dpi / 72
        mat = fitz.Matrix(zoom, zoom)

        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        if output_path:
            img.save(output_path)
            logger.info(f"Saved page {page_num} image to {output_path}")

        return img


def extract_all_pages_text(pdf_path: str) -> List[str]:
    """
    Extract text from all pages of a PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of strings, one per page
    """
    with PDFExtractor(pdf_path) as extractor:
        metadata = extractor.get_pdf_metadata()
        pages_text = []

        for page_num in range(metadata.page_count):
            text = extractor.extract_full_text(page_num)
            pages_text.append(text)

    return pages_text


def extract_all_pages_blocks(pdf_path: str) -> List[List[PDFBlock]]:
    """
    Extract text blocks with positions from all pages of a PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of lists of PDFBlock objects, one list per page
    """
    with PDFExtractor(pdf_path) as extractor:
        metadata = extractor.get_pdf_metadata()
        all_blocks = []

        for page_num in range(metadata.page_count):
            blocks = extractor.extract_text_with_positions(page_num)
            all_blocks.append(blocks)

    return all_blocks
