"""
PDF generation service for creating text-based comparison reports.
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, red
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import logging
from typing import List, Tuple
from pathlib import Path

from app.models.schemas import PageAnalysis, ComparisonSummary, DifferenceResult
from app.services.pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Generator for creating text-based comparison PDFs."""

    def __init__(
        self,
        source_pdf_path: str,
        copy_pdf_path: str,
        output_path: str,
        dpi: int = 300
    ):
        """
        Initialize the PDF generator.

        Args:
            source_pdf_path: Path to source PDF
            copy_pdf_path: Path to copy PDF
            output_path: Path for output PDF
            dpi: Resolution for rendering pages (not used in text-based approach)
        """
        self.source_pdf_path = source_pdf_path
        self.copy_pdf_path = copy_pdf_path
        self.output_path = output_path
        self.dpi = dpi

    def generate(
        self,
        page_analyses: List[PageAnalysis],
        summary: ComparisonSummary,
        progress_callback=None
    ) -> str:
        """
        Generate the comparison PDF with text-based differences.

        Args:
            page_analyses: List of page analysis results
            summary: Comparison summary
            progress_callback: Optional callback(step: str, progress: int)

        Returns:
            Path to generated PDF
        """
        logger.info(f"Generating text-based comparison PDF: {self.output_path}")

        if progress_callback:
            progress_callback("Generating PDF report...", 90)

        # Create PDF with reportlab
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        # Container for PDF elements
        story = []
        styles = getSampleStyleSheet()

        # Add custom styles
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=HexColor('#34495e'),
            spaceAfter=12,
            spaceBefore=12
        ))

        styles.add(ParagraphStyle(
            name='DiffLabel',
            parent=styles['Normal'],
            fontSize=10,
            textColor=red,
            fontName='Helvetica-Bold'
        ))

        # 1. Title Page
        story.append(Paragraph("PDF Comparison Report", styles['CustomTitle']))
        story.append(Spacer(1, 0.3*inch))

        # 2. Summary Section
        story.append(Paragraph("Comparison Summary", styles['SectionHeading']))

        summary_data = [
            ["Metric", "Value"],
            ["Comparison Date", summary.comparison_date],
            ["LLM Used", summary.llm_used],
            ["Total Pages", str(summary.total_pages)],
            ["Pages with Differences", str(summary.pages_with_differences)],
            ["Overall Similarity Score", f"{summary.similarity_score}%"],
        ]

        summary_table = Table(summary_data, colWidths=[3*inch, 3.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#bdc3c7')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))

        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))

        # 3. Methodology
        story.append(Paragraph("Methodology", styles['SectionHeading']))
        story.append(Paragraph(summary.methodology, styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

        # 4. How to Read This Report
        story.append(Paragraph("How to Read This Report", styles['SectionHeading']))
        story.append(Paragraph(
            "• Each page comparison shows the similarity rating and lists all differences found<br/>"
            "• Differences are categorized by type: Content Change, Addition, Deletion, or Formatting<br/>"
            "• SOURCE text shows what was in the original document<br/>"
            "• COPY text shows what appears in the compared document<br/>"
            "• LLM reasoning explains why each difference was identified",
            styles['Normal']
        ))

        story.append(PageBreak())

        # 5. Page-by-Page Comparison
        story.append(Paragraph("Detailed Page Comparisons", styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))

        for idx, analysis in enumerate(page_analyses):
            if progress_callback:
                progress = 90 + int((idx / len(page_analyses)) * 9)
                progress_callback(f"Formatting page {idx + 1}...", progress)

            self._add_page_comparison(story, analysis, styles)

            # Add page break after each page (except last)
            if idx < len(page_analyses) - 1:
                story.append(PageBreak())

        # Build PDF
        doc.build(story)

        logger.info(f"PDF generated successfully: {self.output_path}")
        return self.output_path

    def _add_page_comparison(self, story, analysis: PageAnalysis, styles):
        """Add a single page comparison to the story."""

        # Page header
        story.append(Paragraph(
            f"<b>Page {analysis.page_number}</b> - Similarity: {analysis.similarity_rating.value}",
            styles['Heading3']
        ))

        # Overall reasoning
        if analysis.overall_reasoning:
            story.append(Paragraph(
                f"<i>{analysis.overall_reasoning}</i>",
                styles['Normal']
            ))
            story.append(Spacer(1, 0.1*inch))

        # If no differences, just note it
        if not analysis.has_differences or len(analysis.differences) == 0:
            story.append(Paragraph(
                "<font color='green'>✓ No significant differences found on this page</font>",
                styles['Normal']
            ))
            story.append(Spacer(1, 0.2*inch))
            return

        # List differences
        story.append(Paragraph(
            f"<b>{len(analysis.differences)} difference(s) found:</b>",
            styles['Normal']
        ))
        story.append(Spacer(1, 0.15*inch))

        for diff_num, diff in enumerate(analysis.differences, 1):
            # Difference number and type
            story.append(Paragraph(
                f"<b>{diff_num}. {diff.type.value}</b>",
                styles['DiffLabel']
            ))

            # Create comparison table
            diff_data = []

            # Header row
            diff_data.append([
                Paragraph("<b>SOURCE</b>", styles['Normal']),
                Paragraph("<b>COPY</b>", styles['Normal'])
            ])

            # Content rows
            source_text = diff.source_text if diff.source_text else "(empty)"
            copy_text = diff.copy_text if diff.copy_text else "(empty)"

            diff_data.append([
                Paragraph(self._escape_text(source_text), styles['Normal']),
                Paragraph(self._escape_text(copy_text), styles['Normal'])
            ])

            # Create table
            diff_table = Table(diff_data, colWidths=[3.25*inch, 3.25*inch])
            diff_table.setStyle(TableStyle([
                # Header row styling
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#e74c3c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

                # Content row styling
                ('BACKGROUND', (0, 1), (0, -1), HexColor('#fff3cd')),  # Source: light yellow
                ('BACKGROUND', (1, 1), (1, -1), HexColor('#d1ecf1')),  # Copy: light blue
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 1), (-1, -1), 8),
                ('RIGHTPADDING', (0, 1), (-1, -1), 8),

                # Grid
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#95a5a6')),
            ]))

            story.append(diff_table)

            # Reasoning
            if diff.reasoning:
                story.append(Spacer(1, 0.08*inch))
                story.append(Paragraph(
                    f"<i>Reasoning: {self._escape_text(diff.reasoning)}</i>",
                    styles['Normal']
                ))

            story.append(Spacer(1, 0.15*inch))

    def _escape_text(self, text: str) -> str:
        """Escape special characters for ReportLab."""
        if not text:
            return ""

        # Limit text length to avoid huge paragraphs
        max_length = 500
        if len(text) > max_length:
            text = text[:max_length] + "..."

        # Escape special characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('\n', '<br/>')

        return text

    def _wrap_text(self, text: str, max_chars: int) -> List[str]:
        """
        Wrap text to fit within max characters per line.

        Args:
            text: Text to wrap
            max_chars: Maximum characters per line

        Returns:
            List of text lines
        """
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length > max_chars:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                current_line.append(word)
                current_length += word_length

        if current_line:
            lines.append(" ".join(current_line))

        return lines
