from dataclasses import dataclass, field
from typing import Any

from app.config import CHUNK_SIZE


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any]
    embedding: list[float] | None = field(default=None)


def chunk_document(doc, chunk_size: int = CHUNK_SIZE, extra_meta: dict | None = None) -> list[Chunk]:
    paragraphs = [p.strip() for p in doc.body.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    current = ""
    base_meta = {
        "type": "story" if extra_meta else "document",
        "title": doc.title,
        "date": doc.date,
        "source": doc.source,
        "prid": doc.prid,
        "url": doc.url,
        "filepath": doc.filepath,
        "images": [],
    }
    if extra_meta:
        base_meta.update(extra_meta)

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(Chunk(text=current, metadata=dict(base_meta)))
            current = para
    if current:
        chunks.append(Chunk(text=current, metadata=dict(base_meta)))

    return chunks
