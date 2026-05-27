"""
services/pdf_extractor.py — PDF text and image extraction
Uses PyMuPDF (fitz) for robust PDF parsing.
Falls back to a basic text extraction if fitz is not installed.
"""

import os
from pathlib import Path

# Try to import PyMuPDF; if not available, we'll use the fallback
_HAS_FITZ = False
try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    fitz = None


def _require_fitz() -> None:
    """Raise a helpful error if PyMuPDF is not installed."""
    if not _HAS_FITZ:
        raise ImportError(
            "PyMuPDF is required for PDF extraction. "
            "Install it with: pip install PyMuPDF"
        )


def _validate_pdf(filepath: str) -> Path:
    """Validate that the file exists and is a PDF. Returns resolved Path."""
    path = Path(filepath).resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() not in {".pdf"}:
        raise ValueError(f"Not a PDF file: {path}")
    return path


def extract_text(filepath: str) -> str:
    """Extract all text from every page of a PDF file.

    Args:
        filepath: Path to the PDF file.

    Returns:
        Concatenated text from all pages, separated by newlines.
    """
    path = _validate_pdf(filepath)

    if _HAS_FITZ:
        doc = fitz.open(str(path))
        try:
            pages_text = []
            for page in doc:
                text = page.get_text("text")
                if text.strip():
                    pages_text.append(text)
            return "\n\n".join(pages_text)
        finally:
            doc.close()
    else:
        return _fallback_extract_text(path)


def extract_images(
    filepath: str,
    output_dir: str | None = None,
) -> list[str]:
    """Extract embedded images from a PDF and save them as PNG files.

    Args:
        filepath: Path to the PDF file.
        output_dir: Directory to save extracted images. Defaults to
                    a subfolder next to the PDF named "<pdfname>_images".

    Returns:
        List of file paths to the extracted PNG images.
    """
    path = _validate_pdf(filepath)
    _require_fitz()

    if output_dir is None:
        output_dir = str(path.parent / f"{path.stem}_images")

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(str(path))
    saved_paths: list[str] = []

    try:
        for page_num, page in enumerate(doc):
            image_list = page.get_images(full=True)

            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]

                try:
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue

                    image_bytes = base_image["image"]
                    image_ext = base_image.get("ext", "png")

                    # Always save as PNG for consistency
                    out_name = f"page{page_num + 1}_img{img_index + 1}.png"
                    out_path = os.path.join(output_dir, out_name)

                    with open(out_path, "wb") as f:
                        f.write(image_bytes)

                    saved_paths.append(out_path)
                except Exception:
                    # Skip images that fail to extract rather than aborting
                    continue
    finally:
        doc.close()

    return saved_paths


def page_count(filepath: str) -> int:
    """Return the number of pages in a PDF file.

    Args:
        filepath: Path to the PDF file.

    Returns:
        Integer page count.
    """
    path = _validate_pdf(filepath)
    _require_fitz()

    doc = fitz.open(str(path))
    try:
        return doc.page_count
    finally:
        doc.close()


def get_page_text(filepath: str, page_num: int) -> str:
    """Extract text from a single page of a PDF (0-indexed).

    Args:
        filepath: Path to the PDF file.
        page_num: Zero-based page index (0 = first page).

    Returns:
        Text content of the specified page.
    """
    path = _validate_pdf(filepath)
    _require_fitz()

    doc = fitz.open(str(path))
    try:
        if page_num < 0 or page_num >= doc.page_count:
            raise IndexError(
                f"Page {page_num} is out of range. "
                f"PDF has {doc.page_count} pages (0-{doc.page_count - 1})."
            )
        page = doc[page_num]
        return page.get_text("text")
    finally:
        doc.close()


# ── fallback: basic text extraction without PyMuPDF ────────────────

def _fallback_extract_text(path: Path) -> str:
    """Minimal PDF text extraction fallback when PyMuPDF is unavailable.

    This regex-based approach only works for simple text-based PDFs.
    It strips binary streams and attempts to recover readable strings.
    """
    try:
        raw = path.read_bytes()

        # Decode what we can; skip undecodable bytes
        text = raw.decode("latin-1", errors="ignore")

        # Remove common PDF binary noise
        lines = text.splitlines()
        clean: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Skip PDF structure lines and very short binary lines
            if (
                not stripped
                or stripped.startswith(("%", "endobj", "endstream", "xref", "trailer"))
                or len(stripped) < 3
            ):
                continue
            # Filter lines that are mostly printable ASCII
            printable = sum(1 for c in stripped if c.isprintable() or c in "\t ")
            if printable / len(stripped) > 0.85:
                clean.append(stripped)

        result = "\n".join(clean)
        if not result.strip():
            return (
                "[PyMuPDF not installed — fallback extraction found no readable text. "
                "Install PyMuPDF for full PDF support: pip install PyMuPDF]"
            )
        return (
            "[Extracted with basic fallback — some formatting may be lost. "
            "Install PyMuPDF for better results: pip install PyMuPDF]\n\n"
            + result
        )
    except Exception as e:
        return f"Error reading PDF: {e}. Install PyMuPDF for full PDF support: pip install PyMuPDF"
