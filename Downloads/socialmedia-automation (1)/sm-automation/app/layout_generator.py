import json
import os

from PIL import Image

from app.cloud_llm import generate as llm_generate
from app.config import BASE_DIR
from app.image_store import get_image_path

BRANDS_DIR = os.path.join(BASE_DIR, "data", "brands")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

_LOGO_DIMS = None


def _read_logo_dims() -> dict:
    """Read natural aspect ratio of each logo, compute fixed display dimensions. Cached."""
    global _LOGO_DIMS
    if _LOGO_DIMS is not None:
        return _LOGO_DIMS

    logos = {
        "nicdc-logo":   {"src": "nicdc-logo.png",   "width": 80},
        "dpiit-logo":   {"src": "dpiit-logo.png",   "width": 60},
        "web-logo":     {"src": "web-logo.png",      "width": 40},
        "x-logo":       {"src": "x-logo.png",        "width": 40},
        "linkedin-logo":{"src": "linkedin-logo.png", "width": 40},
    }
    result = {}
    for eid, info in logos.items():
        fpath = os.path.join(ASSETS_DIR, info["src"])
        w = info["width"]
        h = w
        try:
            with Image.open(fpath) as img:
                nat_w, nat_h = img.size
                if nat_w > 0:
                    h = round(w * nat_h / nat_w)
        except Exception:
            pass
        result[eid] = {"width": w, "height": h}
    _LOGO_DIMS = result
    return result


def _fit_image(nat_w: int, nat_h: int, slot_w: int, slot_h: int) -> tuple[int, int]:
    """Calculate display dimensions that preserve the natural aspect ratio within a bounding box."""
    if nat_w <= 0 or nat_h <= 0:
        return slot_w, slot_h
    ratio = nat_w / nat_h
    slot_ratio = slot_w / slot_h
    if ratio > slot_ratio:
        dw = slot_w
        dh = int(slot_w / ratio)
    else:
        dh = slot_h
        dw = int(slot_h * ratio)
    return max(dw, 1), max(dh, 1)


# ── Text Generation (LLM) ────────────────────────────

TEXT_SYSTEM_PROMPT = """You are a social media copywriter for NICDC (National Industrial Corridor Development Corporation) under DPIIT, Government of India.

Given a topic and body text, generate social media post content as JSON.

STRICT WORD LIMITS:
- headline: bold, concise, MAX 8 words
- body: exactly 3 bullet points, each starting with •, separated by \\n. Each bullet MAX 12 words with specific facts, numbers, and names.
- stat_label: MAX 8 words describing what the statistic represents

Return ONLY valid JSON with these fields:
{
  "headline": "Bold max-8-word headline",
  "body": "• Bullet point one (max 12 words)\\n• Bullet point two (max 12 words)\\n• Bullet point three (max 12 words)",
  "stat_number": "A key statistic (e.g. USD 863B)",
  "stat_label": "Max 8 word description",
  "source": "Source: PIB | nicdc.in"
}

RULES:
- Headline: bold, concise, max 8 words. No quotation marks.
- Body: exactly 3 bullet points, each starting with •, separated by \\n. Each bullet max 12 words with specific facts, numbers, and names.
- stat_number: extract the most impressive number from the text.
- stat_label: short description of what the number represents, max 8 words.
- source: always start with "Source:" followed by the origin.
- Return ONLY the JSON object. No markdown, no explanation."""


def _enforce_word_limits(content: dict) -> dict:
    """Code-level enforcement of word limits. Cannot be skipped by the LLM."""
    # Headline: max 8 words
    headline = content.get("headline", "")
    words = headline.split()
    if len(words) > 8:
        content["headline"] = " ".join(words[:8])

    # Body: 3 bullets, each max 12 words
    body = content.get("body", "")
    lines = body.split("\n")
    bullets = [l for l in lines if l.strip().startswith(("•", "-", "*"))]
    enforced = []
    for b in bullets[:3]:
        # Strip the bullet prefix
        prefix = b.strip()[0]  # •, -, or *
        btext = b.strip()[1:].strip()
        bwords = btext.split()
        if len(bwords) > 12:
            bwords = bwords[:12]
        enforced.append(f"{prefix} {' '.join(bwords)}")
    content["body"] = "\n".join(enforced)

    # stat_label: max 8 words
    stat_label = content.get("stat_label", "")
    sl_words = stat_label.split()
    if len(sl_words) > 8:
        content["stat_label"] = " ".join(sl_words[:8])

    return content


async def _generate_text(
    topic: str,
    text: str,
    category: str,
    temperature: float = 0.4,
) -> dict:
    """Use LLM to generate text content only (headline, body, stats, source)."""
    prompt = f"""Topic: {topic}
Category: {category}

Body text:
{text[:3000]}

Generate social media post content as JSON. Return ONLY the JSON."""

    raw = await llm_generate(
        prompt=prompt,
        system_instruction=TEXT_SYSTEM_PROMPT,
        temperature=temperature,
        max_tokens=8192,
    )

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        content = json.loads(raw)
    except json.JSONDecodeError:
        content = {
            "headline": topic[:80],
            "body": f"• {text[:300]}",
            "stat_number": "",
            "stat_label": "",
            "source": "Source: PIB | nicdc.in",
        }

    content.setdefault("headline", topic[:80])
    content.setdefault("body", f"• {text[:300]}")
    content.setdefault("stat_number", "")
    content.setdefault("stat_label", "")
    content.setdefault("source", "Source: PIB | nicdc.in")

    # Enforce max 3 bullet points
    body_lines = content["body"].split("\n")
    bullets = [l for l in body_lines if l.strip().startswith(("•", "-", "*"))]
    if len(bullets) > 3:
        content["body"] = "\n".join(bullets[:3])

    # Enforce strict word limits
    content = _enforce_word_limits(content)

    return content


# ── Single Variation Generation (no LLM) ──────────────


async def generate_layout(
    topic: str,
    text: str,
    images: list[str],
    category: str,
    temperature: float = 0.4,
) -> dict:
    brand = await load_brand(category)
    text_content = await _generate_text(topic, text, category, temperature)

    # Read image dimensions so frontend can fit them correctly
    image_meta = []
    for img in images:
        path = get_image_path(img)
        w, h = 1080, 1080
        if os.path.isfile(path):
            try:
                with Image.open(path) as pil_img:
                    w, h = pil_img.size
            except Exception:
                pass
        image_meta.append({"src": f"/images/{img}", "width": w, "height": h})

    return {
        "brand": {
            "palette": brand.get("palette", {}),
            "fonts": brand.get("fonts", {}),
            "logo": brand.get("logo", "/assets/nicdc-logo.png"),
            "dpiit_logo": brand.get("dpiit_logo", "/assets/dpiit-logo.png"),
        },
        "content": text_content,
        "images": image_meta,
    }


# ── Layout Variations (deterministic) ─────────────────


async def load_brand(category: str) -> dict:
    """Brand comes from the categories table (created/edited in the
    dashboard); legacy data/brands/*.json is a read-only fallback."""
    slug = category.lower().strip().replace(" ", "-")

    from app.database import async_session
    from app.repositories.category_repo import CategoryRepo
    async with async_session() as session:
        cat = await CategoryRepo(session).get(slug)
    if cat:
        return cat

    path = os.path.join(BRANDS_DIR, f"{slug}.json")
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    raise FileNotFoundError(f"Category '{category}' not found. Create it in the dashboard under Categories.")


async def generate_layout_variations(
    topic: str,
    text: str,
    images: list[str],
    category: str,
    temperature: float = 0.4,
) -> dict:
    """Generate 2 distinct layout variations using the deterministic engine.

    Returns:
        { brand, content, images, variations: [state1, state2] }
    """
    from app.enhancement import enhance_layout, _ensure_color_diversity
    from app.layout_engine import build_variation

    brand = await load_brand(category)
    text_content = await _generate_text(topic, text, category, temperature)

    image_meta = []
    for img in images:
        path = get_image_path(img)
        w, h = 1080, 1080
        if os.path.isfile(path):
            try:
                with Image.open(path) as pil_img:
                    w, h = pil_img.size
            except Exception:
                pass
        image_meta.append({"src": f"/images/{img}", "width": w, "height": h})

    brand_info = {
        "palette": brand.get("palette", {}),
        "fonts": brand.get("fonts", {}),
        "logo": brand.get("logo", "/assets/nicdc-logo.png"),
        "dpiit_logo": brand.get("dpiit_logo", "/assets/dpiit-logo.png"),
    }

    palette = brand.get("palette", {})

    # Build both variations deterministically (no LLM for layout geometry)
    variations = []
    for variant in ("classic", "split"):
        state = build_variation(variant, text_content, image_meta, brand_info)

        try:
            enhanced = await enhance_layout(
                design_state=state,
                brand=brand_info,
                content=text_content,
                temperature=0.6,
            )
            enhanced["elements"] = _ensure_color_diversity(enhanced.get("elements", []), palette)
            variations.append(enhanced)
        except Exception:
            state["elements"] = _ensure_color_diversity(state["elements"], palette)
            variations.append(state)

    return {
        "brand": brand_info,
        "content": text_content,
        "images": image_meta,
        "variations": variations,
    }
