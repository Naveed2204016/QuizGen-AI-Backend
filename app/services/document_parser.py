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

    useful = [section for section in sections if len(section.text) >= 20]
    if not useful:
        raise ValueError("No readable text was found. Scanned/image-only files require OCR.")
    return useful
