"""
Annotation utilities for drawing difference markers on PDF images.
"""
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple
import logging

from app.models.schemas import BoundingBox, DifferenceResult

logger = logging.getLogger(__name__)


class AnnotationDrawer:
    """Utility class for drawing annotations on PDF page images."""

    def __init__(self, image: Image.Image):
        """
        Initialize the annotation drawer.

        Args:
            image: PIL Image to annotate
        """
        self.image = image.copy()  # Work on a copy
        self.draw = ImageDraw.Draw(self.image, "RGBA")

    def draw_red_box(
        self,
        bbox: BoundingBox,
        label: str = None,
        line_width: int = 2,
        transparency: int = 77  # 30% transparency (255 * 0.3)
    ) -> None:
        """
        Draw a red bounding box on the image.

        Args:
            bbox: Bounding box coordinates
            label: Optional label text to display
            line_width: Width of the border line
            transparency: Alpha value for fill (0-255, lower is more transparent)
        """
        # Convert bbox coordinates
        x1 = int(bbox.x)
        y1 = int(bbox.y)
        x2 = int(bbox.x + bbox.width)
        y2 = int(bbox.y + bbox.height)

        # Draw filled rectangle with transparency
        fill_color = (255, 0, 0, transparency)  # Red with transparency
        self.draw.rectangle([x1, y1, x2, y2], fill=fill_color, outline=None)

        # Draw border
        border_color = (255, 0, 0, 255)  # Solid red
        for i in range(line_width):
            self.draw.rectangle(
                [x1 + i, y1 + i, x2 - i, y2 - i],
                outline=border_color,
                width=1
            )

        # Draw label if provided
        if label:
            self._draw_label(x1, y1, label)

    def _draw_label(self, x: int, y: int, text: str) -> None:
        """
        Draw a label above the bounding box.

        Args:
            x: X coordinate
            y: Y coordinate
            text: Label text
        """
        try:
            # Try to use a reasonable font size
            font_size = 14
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

            # Calculate text size
            bbox = self.draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Draw background for label
            label_padding = 3
            label_bg = (255, 0, 0, 200)  # Semi-transparent red
            self.draw.rectangle(
                [
                    x - label_padding,
                    y - text_height - label_padding * 2,
                    x + text_width + label_padding,
                    y
                ],
                fill=label_bg
            )

            # Draw text
            self.draw.text(
                (x, y - text_height - label_padding),
                text,
                fill=(255, 255, 255, 255),  # White
                font=font
            )
        except Exception as e:
            logger.warning(f"Could not draw label: {e}")

    def add_difference_markers(
        self,
        differences: List[DifferenceResult],
        offset_x: int = 0,
        offset_y: int = 0
    ) -> None:
        """
        Add markers for multiple differences.

        Args:
            differences: List of differences to mark
            offset_x: X offset for all boxes (for side-by-side layout)
            offset_y: Y offset for all boxes
        """
        for idx, diff in enumerate(differences, start=1):
            if diff.bbox:
                # Adjust bbox with offset
                adjusted_bbox = BoundingBox(
                    x=diff.bbox.x + offset_x,
                    y=diff.bbox.y + offset_y,
                    width=diff.bbox.width,
                    height=diff.bbox.height
                )

                # Draw box with number label
                self.draw_red_box(adjusted_bbox, label=str(idx))

    def get_annotated_image(self) -> Image.Image:
        """
        Get the annotated image.

        Returns:
            PIL Image with annotations
        """
        return self.image


def annotate_image(
    image: Image.Image,
    differences: List[DifferenceResult],
    offset_x: int = 0,
    offset_y: int = 0
) -> Image.Image:
    """
    Convenience function to annotate an image with differences.

    Args:
        image: PIL Image to annotate
        differences: List of differences to mark
        offset_x: X offset for all boxes
        offset_y: Y offset for all boxes

    Returns:
        Annotated PIL Image
    """
    drawer = AnnotationDrawer(image)
    drawer.add_difference_markers(differences, offset_x, offset_y)
    return drawer.get_annotated_image()


def create_legend_image(width: int, height: int = 50) -> Image.Image:
    """
    Create a legend image explaining the red boxes.

    Args:
        width: Width of the legend image
        height: Height of the legend image

    Returns:
        PIL Image with legend
    """
    # Create white background
    legend = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(legend)

    # Draw a small red box as example
    box_size = 20
    margin = 10
    draw.rectangle(
        [margin, margin, margin + box_size, margin + box_size],
        outline=(255, 0, 0),
        width=2
    )

    # Add text explanation
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    text = "Red boxes indicate differences between source and copy"
    draw.text(
        (margin + box_size + 10, margin + 5),
        text,
        fill=(0, 0, 0),
        font=font
    )

    return legend
