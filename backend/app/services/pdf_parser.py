"""PDF text extraction using PyMuPDF (fitz)."""
import io
from typing import List
from dataclasses import dataclass, field
from app.utils.helpers import logger


@dataclass
class ParsedResume:
    """Result of PDF parsing."""
    pages: List[str] = field(default_factory=list)
    raw_text: str = ""
    page_count: int = 0
    is_scanned: bool = False


async def parse_pdf(file_bytes: bytes) -> ParsedResume:
    """Extract text from PDF bytes.

    Uses PyMuPDF for robust multi-page and Chinese text extraction.
    Sets is_scanned=True if very little text is found (image-based PDF).
    """
    import fitz  # PyMuPDF — lazy import to keep cold-start fast

    result = ParsedResume()

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        result.page_count = doc.page_count

        all_text_parts = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text:
                all_text_parts.append(text.strip())
            result.pages.append(text.strip())

        doc.close()
        result.raw_text = "\n\n".join(all_text_parts)

        # Detect scanned/image PDFs (very little extractable text)
        if len(result.raw_text.strip()) < 50 and result.page_count > 0:
            result.is_scanned = True
            logger.warning("PDF appears to be image-based (scanned document)")

    except Exception as e:
        logger.error(f"PDF parsing failed: {e}")
        raise ValueError(f"Failed to parse PDF: {str(e)}")

    return result


def validate_pdf(file_bytes: bytes, filename: str) -> None:
    """Validate that uploaded file is a genuine PDF.

    Raises ValueError if validation fails.
    """
    # Check file extension
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are accepted")

    # Check PDF magic bytes: %PDF
    if len(file_bytes) < 4 or file_bytes[:4] != b"%PDF":
        raise ValueError("File is not a valid PDF (invalid header)")

    # Check minimum size
    if len(file_bytes) < 100:
        raise ValueError("PDF file appears to be empty or corrupted")
