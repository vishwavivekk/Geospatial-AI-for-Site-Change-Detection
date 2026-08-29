import json
import re

import httpx

from app.config import LLAMA_CPP_BASE_URL, MODEL_NAME, PROMPT_TEMPLATE_PATH
from app.retriever import retrieve


def _load_system_prompt() -> str:
    with open(PROMPT_TEMPLATE_PATH) as f:
        return f.read().strip()


def _format_context(results: list[dict]) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        header = f"[{i}] {meta.get('title', 'Untitled')} ({meta.get('date', '')})"
        parts.append(f"{header}\n{r['text']}")
    return "\n\n".join(parts)


def _parse_json(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    idx = text.find("{")
    if idx == -1:
        return None
    while idx < len(text):
        try:
            obj, end = decoder.raw_decode(text, idx)
            return obj
        except json.JSONDecodeError:
            idx = text.find("{", idx + 1)
            if idx == -1:
                return None
    return None


async def generate_post(topic: str, k: int = 5) -> dict:
    results = await retrieve(topic, k=k)
    context = _format_context(results)
    system_prompt = _load_system_prompt()

    user_prompt = (
        f"Relevant context:\n{context}\n\n"
        f"Topic: {topic}\n\n"
        "Create a professional social media post. Return ONLY valid JSON."
    )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{LLAMA_CPP_BASE_URL}/v1/chat/completions",
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "n_predict": 1024,
            },
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]

    parsed = _parse_json(raw)

    return {
        "raw": raw,
        "parsed": parsed,
        "sources": [
            {
                "title": r["metadata"]["title"],
                "url": r["metadata"]["url"],
                "images": r["metadata"].get("images", []),
            }
            for r in results
        ],
    }
