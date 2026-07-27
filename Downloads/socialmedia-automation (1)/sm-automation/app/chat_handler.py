import json

from app.cloud_llm import generate as llm_generate

SYSTEM_PROMPT = """You are a professional social media graphic designer for NICDC (National Industrial Corridor Development Corporation). You help users edit an existing 1080x1080 Instagram post design using natural language.

The user will provide you with the current design JSON (a Konva.js layout) and a request for changes.

Your job:
1. Analyze the current design and the user's request.
2. Apply the requested changes to the design.
3. Return a brief text explanation of what you changed, followed by the complete updated design JSON.

RESPONSE FORMAT (strict):
- First, write a short text explanation (1-3 sentences) of what you changed or your response.
- Then, on a new line, write the separator: ---DESIGN---
- Then, on the next lines, write the complete updated design JSON object (no markdown fences, no backticks).
- If the user's message is conversational (greeting, question, not a design change), respond with text only — do NOT include the ---DESIGN--- separator.

Example:
I've moved the headline to the top and increased its font size to 56px for better visibility.
---DESIGN---
{"canvas":{"width":1080,"height":1080,"background":"#F3F7FA"},"elements":[...]}

DESIGN RULES:
- Always return the COMPLETE design JSON when making changes — not just the changed elements.
- Preserve all elements the user did not ask to change.
- Use only these element types: rect, text, image, circle, ellipse, line, path, star, ring, polygon.
- Maintain 1080x1080 canvas dimensions.
- Each element needs: id (string), type (string), locked (boolean), attrs (object).
- Common text attrs: x, y, text, fontSize, fontFamily, fontStyle, fill, align, width, wrap, padding, lineHeight.
- Common rect attrs: x, y, width, height, fill, stroke, strokeWidth, cornerRadius, opacity.
- Common image attrs: x, y, width, height, src, cornerRadius, opacity.
- Common circle attrs: x, y, radius, fill, stroke, strokeWidth, opacity.
- Return ONLY the text + separator + JSON. No markdown fences, no extra commentary."""

DESIGN_CONTEXT_HEADER = "Here is the current design state (Konva.js layout JSON):\n\n"

MAX_HISTORY_TURNS = 10


def _build_messages(
    design_state: dict,
    message: str,
    history: list[dict],
) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    design_json = json.dumps(design_state, indent=2)
    design_context = (
        f"{DESIGN_CONTEXT_HEADER}```json\n{design_json}\n```"
    )

    history_slice = history[-MAX_HISTORY_TURNS * 2 :]
    if history_slice:
        first = history_slice[0]
        if first.get("role") == "user":
            history_slice[0] = {
                "role": "user",
                "content": design_context + "\n\n" + first["content"],
            }
        for turn in history_slice:
            messages.append({
                "role": turn.get("role", "user"),
                "content": turn.get("content", ""),
            })
        messages.append({"role": "user", "content": f"User request: {message}"})
    else:
        messages.append({"role": "user", "content": design_context + "\n\nUser request: " + message})

    return messages


def _parse_response(raw: str) -> tuple[str, dict | None]:
    marker = "---DESIGN---"
    if marker in raw:
        parts = raw.split(marker, 1)
        text_part = parts[0].strip()
        json_part = parts[1].strip()
        if json_part.startswith("```"):
            json_part = json_part.split("\n", 1)[-1]
            json_part = json_part.rsplit("```", 1)[0].strip()
        try:
            design = json.loads(json_part)
            return text_part, design
        except json.JSONDecodeError:
            return raw.strip(), None
    return raw.strip(), None


async def chat_edit(
    design_state: dict,
    message: str,
    history: list[dict] | None = None,
) -> dict:
    if history is None:
        history = []

    messages = _build_messages(design_state, message, history)

    raw = await llm_generate(
        temperature=0.4,
        max_tokens=8192,
        messages=messages,
    )

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()

    text, design = _parse_response(raw)

    if design is not None:
        design.setdefault("canvas", {"width": 1080, "height": 1080, "background": "#F3F7FA"})
        design.setdefault("elements", [])
        for idx, el in enumerate(design["elements"]):
            el.setdefault("locked", False)
            el.setdefault("attrs", {})
            if "id" not in el:
                el["id"] = f"el-{idx}"

    return {"text": text, "design": design}
