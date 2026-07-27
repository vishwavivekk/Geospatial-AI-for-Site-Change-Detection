import json
import os

from PIL import Image

from app.cloud_llm import generate as llm_generate
from app.config import BASE_DIR
from app.image_store import get_image_path

BRANDS_DIR = os.path.join(BASE_DIR, "data", "brands")

SUPPORTED_TYPES = {
    "rect", "text", "image", "circle", "ellipse",
    "line", "path", "star", "ring", "polygon", "group",
}

SYSTEM_PROMPT = """You are a professional social media graphic designer for NICDC (National Industrial Corridor Development Corporation). Given a story topic, body text, image URLs (with dimensions), and brand guidelines, generate a layout JSON for a 1080x1080 Instagram square post.

The layout JSON schema is:
{
  "canvas": { "width": 1080, "height": 1080, "background": "#hex" },
  "elements": [
    {
      "id": "unique-id",
      "type": "<element-type>",
      "locked": false,
      "attrs": { <type-specific attributes> }
    }
  ]
}

Supported element types:
- rect: x, y, width, height, fill, stroke, strokeWidth, cornerRadius, opacity, shadowBlur, shadowColor
- text: x, y, text, fontSize, fontFamily, fontStyle, fontVariant, fill, align, width, wrap, padding, lineHeight
- image: x, y, width, height, src, cornerRadius, opacity
- circle: x, y, radius, fill, stroke, strokeWidth, opacity
- ellipse: x, y, radiusX, radiusY, fill, stroke, opacity
- line: points[], stroke, strokeWidth, closed, fill, tension
- path: data (SVG path), fill, stroke, scaleX, scaleY
- star: x, y, numPoints, innerRadius, outerRadius, fill, stroke
- ring: x, y, innerRadius, outerRadius, fill, stroke
- polygon: x, y, sides, radius, fill, stroke, opacity
- group: x, y, children (nested element array), draggable

Design rules:
1. Always include a full-width background rect (1080x1080) using brand background color.
2. Use brand colors for headings, accents, and decorative elements.
3. Use brand heading font for headlines, body font for body text.
4. Headline should be prominent (fontSize 48-60), body text readable (fontSize 22-28).
5. You MUST include EVERY provided image as an image element in the layout. Do not skip any.
6. Use the image dimensions provided to set correct width and height on image elements.
7. Add decorative elements (circles, lines, paths) at low opacity for visual interest.
8. Text width should allow adequate margins (typically 80-100px from edges).
9. Keep the layout balanced — don't crowd elements.
10. Use wrap: "word" for text elements so they flow correctly.
11. If multiple images are provided, arrange them in an attractive grid or collage.
12. The tone should match the brand tone description.

Return ONLY valid JSON. No markdown fences, no explanation."""


def load_brand(category: str) -> dict:
    category = category.lower()
    path = os.path.join(BRANDS_DIR, f"{category}.json")
    if not os.path.isfile(path):
        path = os.path.join(BRANDS_DIR, "news.json")
    with open(path) as f:
        return json.load(f)


def _get_image_info(images: list[str]) -> tuple[list[dict], str]:
    """Return (image_info_list, formatted_prompt_lines)."""
    info_list: list[dict] = []
    lines: list[str] = []
    for img in images:
        path = get_image_path(img)
        w, h = None, None
        if os.path.isfile(path):
            try:
                with Image.open(path) as pil_img:
                    w, h = pil_img.size
            except Exception:
                pass
        info_list.append({"filename": img, "width": w, "height": h})
        if w and h:
            lines.append(f"  - /images/{img} ({w}×{h})")
        else:
            lines.append(f"  - /images/{img} (unknown size)")
    if not lines:
        lines.append("  (no images provided)")
    return info_list, "\n".join(lines)


def _auto_place_images(
    layout: dict,
    images: list[str],
    image_info: list[dict],
) -> dict:
    """Ensure every provided image appears as an image element."""
    existing_srcs: set[str] = set()
    for el in layout.get("elements", []):
        if el.get("type") == "image":
            src = el.get("attrs", {}).get("src", "")
            existing_srcs.add(src)

    count = len(images)
    next_id = len(layout.get("elements", []))

    layouts = {
        1: [(80, 540, 920, 460)],
        2: [(80, 540, 440, 460), (560, 540, 440, 460)],
        3: [(80, 540, 290, 460), (395, 540, 290, 460), (710, 540, 290, 460)],
    }
    positions = layouts.get(count, [(80 + (i % 3) * 340, 540 + (i // 3) * 240, 300, 200) for i in range(count)])

    for i, img in enumerate(images):
        url = f"/images/{img}"
        if url in existing_srcs:
            continue
        info = image_info[i] if i < len(image_info) else {}
        w, h = info.get("width"), info.get("height")
        if w and h:
            aspect = w / h
            pw, ph = positions[i][2], positions[i][3]
            if aspect > pw / ph:
                pw = int(ph * aspect)
            else:
                ph = int(pw / aspect)
        else:
            pw, ph = positions[i][2], positions[i][3]
        x, y = positions[i][0], positions[i][1]
        el = {
            "id": f"img-{i}",
            "type": "image",
            "locked": False,
            "attrs": {
                "src": url,
                "x": x,
                "y": y,
                "width": pw,
                "height": ph,
                "cornerRadius": 16,
                "opacity": 1,
            },
        }
        layout.setdefault("elements", []).append(el)
        next_id += 1

    return layout


async def generate_layout(
    topic: str,
    text: str,
    images: list[str],
    category: str,
    temperature: float = 0.4,
) -> dict:
    brand = load_brand(category)
    image_info, image_lines = _get_image_info(images)

    prompt = f"""Topic: {topic}
Category: {category}
Body text:
{text}

Images (with dimensions):
{image_lines}

Brand guidelines:
{json.dumps(brand, indent=2)}

Generate a single 1080x1080 Instagram post layout following the schema above. Remember: you MUST include an image element for EVERY image listed above."""

    raw = await llm_generate(
        prompt=prompt,
        system_instruction=SYSTEM_PROMPT,
        temperature=temperature,
        max_tokens=8192,
    )

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        layout = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"LLM returned non-JSON response: {raw[:500]!r}")

    layout.setdefault("canvas", {"width": 1080, "height": 1080, "background": "#F3F7FA"})
    layout.setdefault("elements", [])

    for idx, el in enumerate(layout["elements"]):
        if el.get("type") not in SUPPORTED_TYPES:
            el["type"] = "rect"
        el.setdefault("locked", False)
        el.setdefault("attrs", {})
        if el["type"] == "image":
            el["attrs"].setdefault("cornerRadius", 16)
        if "id" not in el:
            el["id"] = f"el-{idx}"

    layout = _auto_place_images(layout, images, image_info)

    layout.setdefault("topic", topic)
    layout.setdefault("category", category)

    return layout
