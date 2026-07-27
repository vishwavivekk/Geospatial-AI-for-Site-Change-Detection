import json

import numpy as np

from app.config import VECTORS_PATH, METADATA_PATH
from app.chunker import Chunk


class VectorStore:
    def __init__(self):
        self.chunks: list[Chunk] = []
        self.vectors: np.ndarray | None = None

    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        self.chunks.extend(chunks)
        new_vecs = np.array([c.embedding for c in chunks], dtype=np.float32)
        if self.vectors is None:
            self.vectors = new_vecs
        else:
            self.vectors = np.vstack([self.vectors, new_vecs])

    def search(self, query_vec: list[float], k: int = 5) -> list[tuple[Chunk, float]]:
        if self.vectors is None or len(self.chunks) == 0:
            return []
        q = np.array(query_vec, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-12)
        vecs_norm = self.vectors / (np.linalg.norm(self.vectors, axis=1, keepdims=True) + 1e-12)
        scores = vecs_norm @ q_norm
        top_k = min(k, len(scores))
        indices = np.argsort(scores)[-top_k:][::-1]
        return [(self.chunks[i], float(scores[i])) for i in indices]

    def clear(self) -> None:
        self.chunks.clear()
        self.vectors = None

    def save(self) -> None:
        if self.vectors is not None:
            np.save(VECTORS_PATH, self.vectors)
        meta = [
            {"text": c.text, "metadata": c.metadata}
            for c in self.chunks
        ]
        with open(METADATA_PATH, "w") as f:
            json.dump(meta, f, indent=2)

    def load(self) -> bool:
        try:
            self.vectors = np.load(VECTORS_PATH)
            with open(METADATA_PATH) as f:
                meta = json.load(f)
            self.chunks = [
                Chunk(text=m["text"], metadata=m["metadata"])
                for m in meta
            ]
            return True
        except (FileNotFoundError, ValueError, KeyError):
            self.clear()
            return False

    def get_stories(self) -> list[dict]:
        groups: dict[str, dict] = {}
        for c in self.chunks:
            if c.metadata.get("type") != "story":
                continue
            key = c.metadata.get("topic", c.metadata.get("title", ""))
            if not key:
                continue
            if key not in groups:
                groups[key] = {
                    "topic": key,
                    "title": c.metadata.get("title", ""),
                    "date": c.metadata.get("date", ""),
                    "category": c.metadata.get("category", ""),
                    "images": [],
                    "text_parts": [],
                }
            groups[key]["text_parts"].append(c.text)
            for img in c.metadata.get("images", []):
                if img not in groups[key]["images"]:
                    groups[key]["images"].append(img)
        result = []
        for g in groups.values():
            result.append({
                "topic": g["topic"],
                "title": g["title"],
                "date": g["date"],
                "category": g["category"],
                "images": g["images"],
                "text": "\n\n".join(g["text_parts"]),
                "chunks": len(g["text_parts"]),
            })
        return result

    def get_story(self, topic: str) -> dict | None:
        chunks: list[Chunk] = []
        images: list[str] = []
        for c in self.chunks:
            if c.metadata.get("type") == "story" and c.metadata.get("topic") == topic:
                chunks.append(c)
                for img in c.metadata.get("images", []):
                    if img not in images:
                        images.append(img)
        if not chunks:
            return None
        meta = chunks[0].metadata
        text = "\n\n".join(c.text for c in chunks)
        return {
            "topic": meta.get("topic", ""),
            "title": meta.get("title", ""),
            "date": meta.get("date", ""),
            "category": meta.get("category", ""),
            "images": images,
            "text": text,
            "chunks": len(chunks),
        }

    def delete_story(self, topic: str) -> list[str]:
        keep_indices: list[int] = []
        images_to_delete: set[str] = set()
        for i, c in enumerate(self.chunks):
            if c.metadata.get("type") == "story" and c.metadata.get("topic") == topic:
                images_to_delete.update(c.metadata.get("images", []))
            else:
                keep_indices.append(i)
        removed = len(self.chunks) - len(keep_indices)
        self.chunks = [self.chunks[i] for i in keep_indices]
        if self.vectors is not None and keep_indices:
            self.vectors = self.vectors[keep_indices]
        elif self.vectors is not None:
            self.vectors = None
        return list(images_to_delete)

    def get_random_chunks(self, n: int = 5) -> list[Chunk]:
        if not self.chunks:
            return []
        seen_titles: set[str] = set()
        result: list[Chunk] = []
        import random
        indices = list(range(len(self.chunks)))
        random.shuffle(indices)
        for i in indices:
            title = self.chunks[i].metadata.get("title", "")
            if title not in seen_titles:
                result.append(self.chunks[i])
                seen_titles.add(title)
            if len(result) >= n:
                break
        return result

    @property
    def size(self) -> int:
        return len(self.chunks)


store = VectorStore()
