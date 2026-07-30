import os
import json
import uuid
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

OPENCODE_BASE = "https://opencode.ai/zen/v1"
OPENCODE_MODEL = "big-pickle"

HERE = Path(__file__).parent
TEMPLATES_DIR = HERE / "templates"
ASSETS_DIR = HERE / "assets"
IMAGES_DIR = HERE / "images"

TEMPLATES_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

app = FastAPI()

IMAGE_CATALOG_PATH = HERE / "image_catalog.json"


def load_image_catalog() -> dict:
    try:
        return json.loads(IMAGE_CATALOG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

AVG_CHAR_FACTOR = 0.50
SAFETY_FACTOR = 0.85
MIN_CHARS = 20


def calc_text_capacity(attrs: dict) -> dict:
    w = attrs.get("width", 200)
    h = attrs.get("height", 40)
    fs = attrs.get("fontSize", 32)
    lh = attrs.get("lineHeight", 1.2)
    cpl = max(1, int(w / (fs * AVG_CHAR_FACTOR)))
    lines = max(1, int(h / (fs * lh)))
    max_chars = max(MIN_CHARS, int(cpl * lines * SAFETY_FACTOR))
    current = attrs.get("text", "")
    if current:
        max_chars = max(max_chars, int(len(current) * 1.5))
    return {"maxChars": max_chars, "maxWords": max(2, int(max_chars / 6))}


def truncate_to_fit(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    brk = truncated.rfind(" ")
    if brk > max_chars * 0.6:
        truncated = truncated[:brk]
    return truncated.strip()


CANVAS_W = 1080


def describe_position(el: dict) -> str:
    a = el.get("attrs", {})
    x = a.get("x", 0)
    y = a.get("y", 0)
    w = a.get("width", 0)
    cx = x + w / 2

    col = 1 + sum(cx >= bound for bound in [CANVAS_W * i // 4 for i in range(1, 4)])

    rows = [
        (0, 300, "Top banner"),
        (300, 550, "Brand area"),
        (550, 690, "Card grid title"),
        (690, 850, "Card grid description"),
        (850, 9999, "Footer"),
    ]
    row = "Layout"
    for y_min, y_max, label in rows:
        if y_min <= y < y_max:
            row = label
            break

    if w > CANVAS_W * 0.25:
        return f"{row}, centered"

    return f"Column {col}, {row}"


ROLE_MAP = {
    "all in one place": "Hero heading — main title of the post",
    "all the tools you need": "Subheading — supporting tagline below hero",
    "explore investor tools": "Section tagline — descriptive sub-header",
    "iclp": "Brand tagline — organization name",
    "estimate land": "Card description — explains a tool/resource",
    "investor": "Card title — name of a tool/resource",
    "cost calculator": "Card title — name of a tool/resource",
    "checklist": "Card description — explains a tool/resource",
    "land allotment": "Card title — name of a tool/resource",
    "step-by-step": "Card description — explains a tool/resource",
    "know your approvals": "Card title — name of a tool/resource",
    "state-wise": "Card description — explains a tool/resource",
    "one platform": "Footer tagline — brand slogan",
    "plan. assess": "Footer tagline — brand slogan",
}


def describe_role(el: dict) -> str:
    label = (el.get("slot_label") or el.get("id", "")).lower().strip()
    for key, role in ROLE_MAP.items():
        if key in label:
            return role
    a = el.get("attrs", {})
    y = a.get("y", 0)
    if y < 300:
        return "Heading or tagline in header area"
    if y < 800:
        if "title" in label:
            return "Card title — short name of a tool or resource"
        return "Card description — brief explanation of a tool or resource"
    return "Footer or brand text"


@app.get("/", response_class=HTMLResponse)
async def index():
    html = (HERE / "editor.html").read_text()
    return HTMLResponse(html)


@app.get("/assets/{filename}")
async def serve_asset(filename: str):
    fpath = ASSETS_DIR / filename
    if not fpath.is_file():
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(str(fpath))


@app.get("/images/{filename}")
async def serve_image(filename: str):
    fpath = IMAGES_DIR / filename
    if not fpath.is_file():
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(str(fpath))


@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    name = uuid.uuid4().hex + ext
    path = IMAGES_DIR / name
    path.write_bytes(await file.read())
    return {"filename": name, "url": f"/images/{name}"}


@app.get("/api/templates")
async def list_templates():
    files = sorted(TEMPLATES_DIR.glob("*.json"))
    result = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            result.append({
                "name": data.get("name", f.stem),
                "filename": f.name,
                "category": data.get("category", ""),
                "description": data.get("description", ""),
            })
        except Exception:
            pass
    return result


@app.get("/api/templates/{filename}")
async def load_template(filename: str):
    fpath = TEMPLATES_DIR / filename
    if not fpath.is_file():
        return HTMLResponse("Not found", status_code=404)
    return json.loads(fpath.read_text())


@app.post("/api/templates")
async def save_template(
    name: str = Form(...),
    category: str = Form(""),
    description: str = Form(""),
    design_state: str = Form(...),
):
    data = json.loads(design_state)
    data["name"] = name
    data["category"] = category
    data["description"] = description
    safe_name = name.lower().replace(" ", "_").replace("/", "_")
    fpath = TEMPLATES_DIR / f"{safe_name}.json"
    fpath.write_text(json.dumps(data, indent=2))
    return {"status": "ok", "filename": fpath.name}


@app.delete("/api/templates/{filename}")
async def delete_template(filename: str):
    fpath = TEMPLATES_DIR / filename
    if fpath.is_file():
        fpath.unlink()
    return {"status": "ok"}


@app.post("/api/generate")
async def generate_content(
    topic: str = Form(...),
    design_state: str = Form(...),
):
    data = json.loads(design_state)
    elements = data.get("elements", [])

    image_catalog = load_image_catalog()

    # Collect text slots
    text_slots = []
    for el in elements:
        if el.get("slot") and el["type"] == "text":
            attrs = el.get("attrs", {})
            cap = calc_text_capacity(attrs)
            text_slots.append({
                "x": attrs.get("x", 0),
                "y": attrs.get("y", 0),
                "w": attrs.get("width", 200),
                "h": attrs.get("height", 40),
                "fontSize": attrs.get("fontSize", 32),
                "fontStyle": attrs.get("fontStyle", "normal"),
                "maxWords": cap["maxWords"],
                "maxChars": cap["maxChars"],
                "position": describe_position(el),
                "role": describe_role(el),
                "element": el,
            })

    # Collect image slots
    image_slots = []
    for el in elements:
        if el.get("slot") and el["type"] == "image":
            src = el.get("attrs", {}).get("src", "")
            fname = src.split("/")[-1] if "/" in src else src
            image_slots.append({
                "position": describe_position(el),
                "role": el.get("slot_label", "icon"),
                "current": image_catalog.get(fname, fname),
                "element": el,
            })

    if not text_slots and not image_slots:
        return {"status": "error", "message": "No slots found in template"}

    cat_lines = "\n".join(
        f"  {k} → {v}"
        for k, v in image_catalog.items()
    ) if image_catalog else "  (no images in catalog)"

    text_block = "\n\n".join(
        f"Slot_{i+1}\n"
        f"  Position: {s['position']}\n"
        f"  Style: {s['fontStyle']} {s['fontSize']}px\n"
        f"  Role: {s['role']}\n"
        f"  Topic: {topic}\n"
        f"  Max ~{s['maxWords']} words ({s['maxChars']} chars)\n"
        f"  → Generate text specific to this topic"
        for i, s in enumerate(text_slots)
    ) if text_slots else "(no text slots)"

    img_block = "\n\n".join(
        f"Slot_{len(text_slots) + i + 1}\n"
        f"  Position: {s['position']}\n"
        f"  Role: {s['role']}\n"
        f"  Topic: {topic}\n"
        f"  → Pick the most relevant bitmap from the catalog for this position and topic"
        for i, s in enumerate(image_slots)
    ) if image_slots else "(no image slots)"

    total_slots = len(text_slots) + len(image_slots)

    system = f"""You are a social media copywriter for ICLP (Industrial Corridor Land Platform) under NICDC, Government of India.

Given a topic, generate text for slot and select relevant bitmaps for image slots in a social media post design.
- Every text slot's content MUST be specific to the given topic — not generic.
- Each slot shows its position, style, role, and a strict word/character limit.
- Card titles: short and bold (2-5 words)
- Descriptions: 1-2 lines explaining the tool/resource
- Headings and taglines: punchy and professional

For TEXT slots (Slot_1 to Slot_{len(text_slots)}): Generate fresh text that fits the limits.
For IMAGE slots (Slot_{len(text_slots) + 1} to Slot_{total_slots}): Pick the most relevant bitmap filename from the catalog.

Return ONLY a JSON object with keys Slot_1 through Slot_{total_slots}. No markdown, no extra text."""

    user = f"""Topic: {topic}

--- TEXT SLOTS (generate fresh text) ---
{text_block}

--- IMAGE SLOTS (pick bitmap from catalog) ---
{img_block}

--- AVAILABLE BITMAPS (pick exact filename from here) ---
{cat_lines}

Return ONLY valid JSON. Slot_1 to Slot_{len(text_slots)} = generated text.
Slot_{len(text_slots) + 1} to Slot_{total_slots} = exact bitmap filename from the catalog above."""

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{OPENCODE_BASE}/chat/completions",
            json={
                "model": OPENCODE_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.4,
                "max_tokens": 65536,
                "reasoning_effort": "low",
            },
        )
        raw = resp.json()
        content = raw["choices"][0]["message"]["content"]

    m = re.search(r'\{[\s\S]*\}', content)
    if not m:
        return {"status": "error", "message": "LLM returned invalid JSON", "raw": content}
    try:
        slot_content = json.loads(m.group())
    except json.JSONDecodeError:
        return {"status": "error", "message": "Failed to parse LLM response", "raw": content}

    # Apply text slot results
    for i, s in enumerate(text_slots):
        key = f"Slot_{i+1}"
        if key in slot_content:
            s["element"]["attrs"]["text"] = truncate_to_fit(slot_content[key], s["maxChars"])

    # Apply image slot results
    for i, s in enumerate(image_slots):
        key = f"Slot_{len(text_slots) + i + 1}"
        if key in slot_content:
            chosen = slot_content[key]
            if chosen in image_catalog and (ASSETS_DIR / chosen).is_file():
                s["element"]["attrs"]["src"] = f"/assets/{chosen}"

    return {"status": "ok", "design_state": data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8770)
