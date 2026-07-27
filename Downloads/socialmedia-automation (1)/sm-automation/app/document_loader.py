from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from app.config import CONTENT_DIR


@dataclass
class Document:
    title: str
    date: str
    source: str
    prid: Optional[str]
    url: Optional[str]
    body: str
    filepath: str


def load_documents(content_dir: str | None = None) -> list[Document]:
    docs = []
    for fpath in sorted(Path(content_dir or CONTENT_DIR).glob("*.md")):
        text = fpath.read_text(encoding="utf-8")
        lines = text.split("\n")

        title = lines[0].lstrip("# ").strip() if lines else ""

        date = ""
        source = ""
        prid: Optional[str] = None
        url: Optional[str] = None

        meta_end = 0
        for i, line in enumerate(lines[1:], start=1):
            stripped = line.strip()
            if stripped.startswith("**Date:"):
                date = stripped.replace("**Date:**", "").strip()
            elif stripped.startswith("**Source:"):
                source = stripped.replace("**Source:**", "").strip()
            elif stripped.startswith("**PRID:"):
                prid = stripped.replace("**PRID:**", "").strip()
            elif stripped.startswith("**URL:"):
                url = stripped.replace("**URL:**", "").strip()
            elif stripped == "":
                continue
            else:
                meta_end = i
                break

        body_start = meta_end
        for i in range(meta_end, len(lines)):
            if lines[i].strip() == "---":
                body_start = i + 1
                break

        body = "\n".join(lines[body_start:]).strip()

        docs.append(Document(
            title=title,
            date=date,
            source=source,
            prid=prid,
            url=url,
            body=body,
            filepath=str(fpath),
        ))

    return docs
