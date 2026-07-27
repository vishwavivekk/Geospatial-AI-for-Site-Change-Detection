import hashlib

import httpx
import numpy as np

from app.config import LLAMA_CPP_BASE_URL, MODEL_NAME

FALLBACK_DIM = 768


def _fallback_embedding(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding used when no llama.cpp server is
    reachable. Keeps the app fully usable locally (stories can still be
    added and retrieved); similarity quality is reduced."""
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big"))
    vec = rng.standard_normal(dim)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


def _store_dim() -> int:
    from app.vector_store import store
    if store.vectors is not None and getattr(store.vectors, "ndim", 0) == 2:
        return int(store.vectors.shape[1])
    return FALLBACK_DIM


async def embed_text(text: str) -> list[float]:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{LLAMA_CPP_BASE_URL}/v1/embeddings",
                json={"input": text, "model": MODEL_NAME},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        return _fallback_embedding(text, _store_dim())


async def embed_batch(texts: list[str]) -> list[list[float]]:
    results: list[list[float]] = []
    for t in texts:
        results.append(await embed_text(t))
    return results
