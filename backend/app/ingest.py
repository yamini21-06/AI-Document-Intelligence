from pathlib import Path
import io
import re

import fitz
import pytesseract

from PIL import Image
from docx import Document as DocxDocument


SUPPORTED = {
    ".pdf",
    ".docx",
    ".txt",
}


def extract_pdf_pages(data: bytes) -> list[tuple[int, str]]:
    """
    Extract text from a PDF.

    First tries normal PDF text extraction using PyMuPDF.

    If a page contains little or no selectable text,
    render that page as an image and use Tesseract OCR.
    """

    pdf = fitz.open(
        stream=data,
        filetype="pdf",
    )

    pages = []

    try:
        for index, page in enumerate(pdf):

            page_number = index + 1

            # -------------------------------------------------
            # First attempt: normal PDF text extraction
            # -------------------------------------------------

            text = page.get_text("text").strip()

            if text:
                pages.append(
                    (
                        page_number,
                        text,
                    )
                )
                continue

            # -------------------------------------------------
            # Fallback: OCR
            # -------------------------------------------------

            # Render the PDF page into an image.
            #
            # 2x scaling gives Tesseract a better image
            # to work with than the default PDF resolution.
            matrix = fitz.Matrix(
                2.0,
                2.0,
            )

            pixmap = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )

            image_bytes = pixmap.tobytes(
                "png"
            )

            image = Image.open(
                io.BytesIO(image_bytes)
            )

            # -------------------------------------------------
            # Run Tesseract OCR
            # -------------------------------------------------

            ocr_text = pytesseract.image_to_string(
                image,
                lang="eng",
            ).strip()

            if ocr_text:
                pages.append(
                    (
                        page_number,
                        ocr_text,
                    )
                )

    finally:
        pdf.close()

    return pages


def extract_pages(
    filename: str,
    data: bytes,
) -> list[tuple[int, str]]:
    """
    Extract text from supported document types.

    Supported:
        PDF
        DOCX
        TXT
    """

    extension = Path(
        filename
    ).suffix.lower()

    # ---------------------------------------------------------
    # PDF
    # ---------------------------------------------------------

    if extension == ".pdf":
        return extract_pdf_pages(data)

    # ---------------------------------------------------------
    # DOCX
    # ---------------------------------------------------------

    if extension == ".docx":

        document = DocxDocument(
            io.BytesIO(data)
        )

        paragraphs = [
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        text = "\n".join(
            paragraphs
        )

        return [
            (
                1,
                text,
            )
        ]

    # ---------------------------------------------------------
    # TXT
    # ---------------------------------------------------------

    if extension == ".txt":

        text = data.decode(
            "utf-8",
            errors="replace",
        )

        return [
            (
                1,
                text,
            )
        ]

    raise ValueError(
        f"Unsupported file type: {extension}"
    )


def normalize(text: str) -> str:
    """
    Clean unnecessary whitespace.
    """

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def chunk_pages(
    pages: list[tuple[int, str]],
    chunk_size: int,
    overlap: int,
) -> list[tuple[int, str]]:
    """
    Split extracted document text into overlapping chunks.

    Returns:
        [(page_number, chunk_text), ...]
    """

    if overlap >= chunk_size:
        raise ValueError(
            "CHUNK_OVERLAP must be smaller "
            "than CHUNK_SIZE"
        )

    result = []

    for page, raw_text in pages:

        text = normalize(
            raw_text
        )

        if not text:
            continue

        start = 0

        while start < len(text):

            end = min(
                start + chunk_size,
                len(text),
            )

            # -------------------------------------------------
            # Try to end the chunk at a natural boundary.
            # -------------------------------------------------

            if end < len(text):

                sentence_boundary = text.rfind(
                    ". ",
                    start,
                    end,
                )

                word_boundary = text.rfind(
                    " ",
                    start,
                    end,
                )

                boundary = max(
                    sentence_boundary,
                    word_boundary,
                )

                if boundary > (
                    start + chunk_size // 2
                ):

                    if text[
                        boundary:boundary + 2
                    ] == ". ":

                        end = boundary + 2

                    else:
                        end = boundary + 1

            # -------------------------------------------------
            # Extract chunk
            # -------------------------------------------------

            piece = text[
                start:end
            ].strip()

            if piece:
                result.append(
                    (
                        page,
                        piece,
                    )
                )

            # -------------------------------------------------
            # Stop at end of document
            # -------------------------------------------------

            if end >= len(text):
                break

            # -------------------------------------------------
            # Move forward while keeping overlap
            # -------------------------------------------------

            start = max(
                end - overlap,
                start + 1,
            )

    return result