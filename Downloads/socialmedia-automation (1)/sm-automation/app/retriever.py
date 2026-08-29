from app.embedder import embed_text
from app.vector_store import store
from app.config import TOP_K


async def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    query_vec = await embed_text(query)
    results = store.search(query_vec, k=k)
    return [
        {
            "text": chunk.text,
            "metadata": chunk.metadata,
            "score": round(score, 4),
        }
        for chunk, score in results
    ]
