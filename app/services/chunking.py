from app.services.document_parser import DocumentSection


def chunk_sections(
    sections: list[DocumentSection], chunk_size: int = 1400, overlap: int = 180
) -> list[dict]:
    chunks: list[dict] = []
    for section in sections:
        text = section.text
        start = 0
        part = 1
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                if boundary > start + chunk_size // 2:
                    end = boundary + 1
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    {
                        "text": piece,
                        "source": section.label,
                        "section_number": section.number,
                        "part": part,
                    }
                )
                part += 1
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks
