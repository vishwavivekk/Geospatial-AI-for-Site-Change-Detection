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

    def load_from_metadata(self, meta_list: list[dict]) -> bool:
        """Load chunks from DB-sourced metadata (used after migration)."""
        if self.vectors is None:
            return False
        self.chunks = [
            Chunk(text=m["text"], metadata=m["metadata"])
            for m in meta_list
        ]
        return True

    def delete_by_topic(self, topic: str) -> None:
        """Remove a story's chunks AND their vector rows so metadata.json
        and vectors.npy stay row-aligned (required by load_from_metadata)."""
        if not self.chunks:
            return
        keep = [i for i, c in enumerate(self.chunks) if c.metadata.get("topic") != topic]
        if len(keep) == len(self.chunks):
            return
        self.chunks = [self.chunks[i] for i in keep]
        if self.vectors is not None:
            self.vectors = self.vectors[keep] if keep else None

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
