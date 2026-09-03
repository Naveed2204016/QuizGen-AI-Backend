import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pptx import Presentation


@dataclass
class DocumentSection:
    number: int
    label: str
    text: str


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def _has_meaningful_text(text: str) -> bool:
    """Reject scanner watermarks and similarly content-free extracted pages."""
    without_scanner_labels = re.sub(
        r"(?im)^\s*(?:scanned\s+by\s+camscanner|camscanner)\s*$", "", text
    ).strip()
    words = re.findall(r"[A-Za-z]{2,}", without_scanner_labels)
    return (
        len(without_scanner_labels) >= 20
        and len(words) >= 5
        and len(set(map(str.lower, words))) >= 4
    )


def extract_document(content: bytes, extension: str) -> list[DocumentSection]:
    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        sections = [
            DocumentSection(index, f"Page {index}", _clean(page.extract_text() or ""))
            for index, page in enumerate(reader.pages, 1)
        ]
    elif extension == ".pptx":
        presentation = Presentation(io.BytesIO(content))
        sections = []
        for index, slide in enumerate(presentation.slides, 1):
            parts: list[str] = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    parts.append(shape.text)
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        parts.append(" | ".join(cell.text for cell in row.cells))
            sections.append(DocumentSection(index, f"Slide {index}", _clean("\n".join(parts))))
    else:
        raise ValueError("Only PDF and PPTX files are supported")

    useful = [section for section in sections if _has_meaningful_text(section.text)]
    if not useful:
        raise ValueError(
            "No readable study text was found. This appears to be a scanned/image-only file and requires OCR."
        )
    return useful
