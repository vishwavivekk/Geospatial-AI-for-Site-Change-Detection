import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

LLM_BASE = "https://opencode.ai/zen/v1"
LLM_MODEL = "big-pickle"

MAX_RETRIES = 3
RETRY_BACKOFF = [2, 4, 8]


async def generate(
    prompt: str = "",
    system_instruction: str = "",
    temperature: float = 0.4,
    max_tokens: int = 8192,
    messages: list[dict] | None = None,
) -> str:
    url = f"{LLM_BASE}/chat/completions"
    if messages is not None:
        messages = list(messages)
    else:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

    body = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()

            try:
                content = data["choices"][0]["message"]["content"]
                if not content:
                    raise RuntimeError(f"LLM returned empty content. Full response: {data}")
                return content
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Unexpected LLM response: {data}") from e

        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            last_error = e
            is_server = isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500
            is_transport = isinstance(e, httpx.TransportError)
            if (is_server or is_transport) and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF[attempt])
                continue
            raise

    raise RuntimeError(f"LLM request failed after {MAX_RETRIES} attempts") from last_error
