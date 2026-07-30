import json

from app.cloud_llm import generate as llm_generate

ENHANCEMENT_SYSTEM_PROMPT = """You are a senior visual designer enhancing a 1080x1080 social media post for NICDC.

You will receive the current Konva.js layout JSON, the brand palette, and a COLOR MAP showing exactly which element uses which color. Your job is to make the design visually compelling using ALL 5 palette colors.

YOUR TASK:
1. Apply the REQUIRED COLOR CHANGES listed in the prompt — these are mandatory recolorings of existing elements.
2. Add decorative shapes as specified for the category.
3. Apply visual enhancements (shadows, spacing adjustments).
4. Return the complete enhanced design JSON.

COLOR RULES:
- All 5 palette colors MUST appear on at least one element.
- Never use colors outside the provided palette.
- The REQUIRED COLOR CHANGES in the prompt tell you exactly what to recolor — follow them precisely.

CATEGORY DECORATION LEVELS:
- News (authoritative): Add 3 decorative shapes. Keep layout clean and institutional. Primary-dominant. Subtle geometry (circles, thin lines).
- Hiring (welcoming): Add 4 decorative shapes. Warmer feel. Use success and highlight more prominently. Include ellipses and rings for approachability.
- Events (celebratory): Add 5 decorative shapes. Maximum visual energy. Stars, rings, overlapping circles. Highlight and accent dominant. Bolder shapes.

DECORATIVE SHAPES:
- Place shapes in empty corners and around edges — never overlapping text content.
- Each shape MUST use a different palette color (no two shapes share the same fill).
- Opacity: 0.03-0.08 for subtlety.
- Use variety: mix circles, ellipses, stars, rings, and polygons. Do not use only circles.
- Shapes should frame the content, not compete with it.

VISUAL ENHANCEMENTS:
- Add subtle shadows (shadowBlur: 10-15, shadowColor: 'rgba(0,0,0,0.15)') to stat-box.
- Ensure headline is visually dominant — largest text, strong color contrast.
- Improve vertical spacing: generous whitespace between sections.

CONSTRAINTS:
- DO NOT modify footer elements: accent-bar, web-logo, web-url, x-logo, linkedin-logo, social-handle
- DO NOT modify header logos: nicdc-logo, dpiit-logo
- DO NOT change text content of any text node
- DO NOT change the canvas background color
- DO NOT remove any existing elements
- DO NOT add new text elements
- Stay within 1080x1080 canvas dimensions
- Use only: rect, circle, ellipse, line, star, ring, polygon

RESPONSE FORMAT:
Return ONLY the complete enhanced design JSON. No markdown, no explanation.
{"canvas":{"width":1080,"height":1080,"background":"..."},"elements":[...]}

Each element: id (string), type (string), locked (boolean), attrs (object).
Attrs: x, y, width, height, fill, stroke, strokeWidth, opacity, cornerRadius, shadowBlur, shadowColor, fontSize, fontFamily, fontStyle, text, align, wrap, radius, points, src."""


def _clean_response(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _is_valid_design(data: dict) -> bool:
    if "elements" not in data:
        return False
    if not isinstance(data["elements"], list):
        return False
    canvas = data.get("canvas", {})
    if canvas.get("width") != 1080 or canvas.get("height") != 1080:
        return False
    for el in data["elements"]:
        if "type" not in el or "id" not in el:
            return False
    return True


def _build_color_map(design_state: dict, palette: dict) -> str:
    hex_to_role = {v: k for k, v in palette.items() if k != "background"}
    lines = []
    for el in design_state.get("elements", []):
        eid = el.get("id", "")
        etype = el.get("type", "")
        attrs = el.get("attrs", {})
        fill = attrs.get("fill", "")
        stroke = attrs.get("stroke", "")
        if fill and fill in hex_to_role:
            lines.append(f"- {eid} ({etype}): fill={fill} ({hex_to_role[fill]})")
        if stroke and stroke in hex_to_role:
            lines.append(f"- {eid} ({etype}): stroke={stroke} ({hex_to_role[stroke]})")
    return "\n".join(lines) if lines else "(no colored elements found)"


def _ensure_color_diversity(elements: list, palette: dict) -> list:
    all_fills = set()
    for el in elements:
        fill = el.get("attrs", {}).get("fill", "")
        if fill:
            all_fills.add(fill)

    missing = [role for role, hex_val in palette.items()
               if hex_val not in all_fills and role != "background"]

    for role in missing:
        hex_val = palette[role]
        if role == "highlight":
            for el in elements:
                if el.get("id") == "stat-num":
                    el.setdefault("attrs", {})["fill"] = hex_val
                    break
        elif role == "success":
            for el in elements:
                if el.get("id") == "cat-tag":
                    el.setdefault("attrs", {})["fill"] = hex_val
                    break
        elif role == "accent":
            for el in elements:
                if el.get("id") == "accent-line":
                    el.setdefault("attrs", {})["stroke"] = hex_val
                    break
        elif role == "primary":
            for el in elements:
                if el.get("id") == "body":
                    el.setdefault("attrs", {})["fill"] = hex_val
                    break

    return elements


def _apply_enhancement(original: dict, enhanced: dict) -> dict:
    """Merge LLM enhancement into original layout.

    POSITION LOCKING: All element positions (x, y, width, height) are always
    taken from the original layout. The LLM can only change colors, fills,
    strokes, and add new decorative shapes. This prevents overlap bugs.
    """
    orig_elements = {el.get("id"): el for el in original.get("elements", [])}
    enh_elements = enhanced.get("elements", [])

    # Position attributes that must always come from the original layout
    POS_ATTRS = {"x", "y", "width", "height", "points"}

    result_elements = []
    seen_ids = set()

    for el in enh_elements:
        eid = el.get("id", "")
        etype = el.get("type", "")

        # New decorative element added by LLM (not in original) — allow it
        if eid not in orig_elements:
            if etype in ("text",) and eid not in orig_elements:
                continue  # don't add new text elements
            el.setdefault("locked", True)
            result_elements.append(el)
            seen_ids.add(eid)
            continue

        # Existing element: merge with locked positions
        orig = orig_elements[eid]
        merged = dict(el)  # shallow copy
        orig_attrs = dict(orig.get("attrs", {}))
        enh_attrs = dict(el.get("attrs", {}))

        # Start with all enhanced attrs (colors, shadows, etc.)
        final_attrs = dict(enh_attrs)

        # Override position/size with original values
        for pa in POS_ATTRS:
            if pa in orig_attrs:
                final_attrs[pa] = orig_attrs[pa]

        merged["attrs"] = final_attrs
        merged["locked"] = orig.get("locked", False)
        result_elements.append(merged)
        seen_ids.add(eid)

    # Ensure all original elements are present (defensive)
    for orig_el in original.get("elements", []):
        eid = orig_el.get("id", "")
        if eid not in seen_ids:
            result_elements.append(orig_el)
            seen_ids.add(eid)

    return {
        "canvas": enhanced.get("canvas", original.get("canvas", {"width": 1080, "height": 1080, "background": "#F3F7FA"})),
        "elements": result_elements,
    }


async def enhance_layout(
    design_state: dict,
    brand: dict,
    content: dict,
    temperature: float = 0.6,
) -> dict:
    palette = brand.get("palette", {})
    color_map = _build_color_map(design_state, palette)

    prompt = f"""Enhance this social media post design. Use ALL 5 palette colors.

BRAND PALETTE:
{json.dumps(palette, indent=2)}

COLOR MAP (current element → color):
{color_map}

REQUIRED COLOR CHANGES:
1. stat-num: fill → {palette.get('highlight', '#E65100')} (highlight)
2. stat-box: fill → {palette.get('highlight', '#E65100')} (highlight), keep opacity 0.1
3. cat-tag: fill → {palette.get('success', '#2E7D32')} (success)
4. Add decorative shapes using DIFFERENT palette colors, opacity 0.03-0.08

CURRENT DESIGN JSON:
{json.dumps(design_state, indent=2)}

Return ONLY the enhanced design JSON."""

    try:
        raw = await llm_generate(
            prompt=prompt,
            system_instruction=ENHANCEMENT_SYSTEM_PROMPT,
            temperature=temperature,
            max_tokens=8192,
        )
        cleaned = _clean_response(raw)
        enhanced = json.loads(cleaned)

        if not _is_valid_design(enhanced):
            result = _apply_enhancement(design_state, design_state)
            result["elements"] = _ensure_color_diversity(result["elements"], palette)
            return result

        result = _apply_enhancement(design_state, enhanced)
        result["elements"] = _ensure_color_diversity(result["elements"], palette)
        return result

    except (json.JSONDecodeError, RuntimeError, Exception):
        result = _apply_enhancement(design_state, design_state)
        result["elements"] = _ensure_color_diversity(result["elements"], palette)
        return result
