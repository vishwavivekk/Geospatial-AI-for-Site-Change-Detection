"""Deterministic layout engine for NICDC social media post variations.

Computes every element's exact x, y, width, height for two structurally
distinct variations. No LLM involved in layout geometry.
"""

import os

from PIL import Image

from app.config import BASE_DIR
from app.layout_generator import _fit_image, _read_logo_dims

ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# ── Constants ──────────────────────────────────────────

W, H, M = 1080, 1080, 60
CW = W - 2 * M  # 960 — content width for full-width layouts

FOOTER_H = 60
FOOTER_Y = H - FOOTER_H  # 1020

STATS_H = 90
STATS_GAP = 20  # gap between stats box and footer

BODY_GAP = 16       # gap between body and stats
DIVIDER_GAP = 12    # gap between divider and body
SUBHEAD_GAP = 24    # gap between subhead and divider
IMG_GAP_TOP = 16    # gap between accent line and image
IMG_GAP_BOT = 30    # gap between image and subhead

LINE_H = 1.4
HEADLINE_LINE_H = 1.15

# Split layout constants
LEFT_W = 540
RIGHT_X = LEFT_W + 30  # 570 — 30px gap for accent bar
RIGHT_W = W - RIGHT_X - M  # 450
RIGHT_CONTENT_X = RIGHT_X + 30  # 600
RIGHT_CONTENT_W = RIGHT_W - 30  # 420 → use 390 for text
IMG_PAD = 30
IMG_SLOT_W = LEFT_W - 2 * IMG_PAD  # 480
IMG_SLOT_MAX_H = 660

# Font families (overridden by brand)
DEFAULT_HFONT = "Georgia, serif"
DEFAULT_BFONT = "Inter, sans-serif"

# Logo sizing — both logos use the same display width
LOGO_WIDTH = 50


# ── Text Height Estimation ────────────────────────────


def _estimate_text_height(
    text: str,
    font_size: int,
    width: int,
    line_height: float = LINE_H,
    font_family: str = DEFAULT_BFONT,
) -> int:
    """Estimate wrapped text height in pixels. Conservative (slightly overestimates)."""
    if not text or not text.strip():
        return 0

    is_serif = "georgia" in font_family.lower() or "serif" in font_family.lower()
    char_ratio = 0.50 if is_serif else 0.55
    avg_char_w = font_size * char_ratio

    total_lines = 0
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            total_lines += 1
            continue
        line_count = 1
        current_w = 0
        for word in words:
            word_w = len(word) * avg_char_w
            if current_w + word_w > width and current_w > 0:
                line_count += 1
                current_w = word_w
            else:
                current_w += word_w + avg_char_w
        total_lines += line_count

    return max(int(total_lines * font_size * line_height), font_size)


# ── Element Builders ───────────────────────────────────


def _text(eid: str, x: int, y: int, text: str, font_size: int,
          font_family: str, fill: str, width: int,
          font_style: str = "", line_height: float = LINE_H,
          align: str = "left", locked: bool = False) -> dict:
    attrs = {
        "x": x, "y": y, "text": text,
        "fontSize": font_size, "fontFamily": font_family,
        "fill": fill, "width": width, "wrap": "word",
        "lineHeight": line_height, "align": align,
    }
    if font_style:
        attrs["fontStyle"] = font_style
    return {"id": eid, "type": "text", "locked": locked, "attrs": attrs}


def _rect(eid: str, x: int, y: int, width: int, height: int,
          fill: str, corner_radius: int = 0, opacity: float = 1.0,
          locked: bool = True) -> dict:
    attrs = {"x": x, "y": y, "width": width, "height": height, "fill": fill}
    if corner_radius:
        attrs["cornerRadius"] = corner_radius
    if opacity < 1.0:
        attrs["opacity"] = opacity
    return {"id": eid, "type": "rect", "locked": locked, "attrs": attrs}


def _image(eid: str, x: int, y: int, width: int, height: int,
           src: str, corner_radius: int = 0, opacity: float = 1.0,
           locked: bool = False) -> dict:
    attrs = {"x": x, "y": y, "width": width, "height": height, "src": src}
    if corner_radius:
        attrs["cornerRadius"] = corner_radius
    if opacity < 1.0:
        attrs["opacity"] = opacity
    return {"id": eid, "type": "image", "locked": locked, "attrs": attrs}


def _line(eid: str, points: list, stroke: str, stroke_width: int = 2,
          locked: bool = True) -> dict:
    return {"id": eid, "type": "line", "locked": locked,
            "attrs": {"points": points, "stroke": stroke, "strokeWidth": stroke_width}}


def _circle(eid: str, x: int, y: int, radius: int, fill: str,
            opacity: float = 1.0, locked: bool = True) -> dict:
    attrs = {"x": x, "y": y, "radius": radius, "fill": fill}
    if opacity < 1.0:
        attrs["opacity"] = opacity
    return {"id": eid, "type": "circle", "locked": locked, "attrs": attrs}


def _ring(eid: str, x: int, y: int, inner_r: int, outer_r: int,
          fill: str = "transparent", stroke: str = "#ccc",
          stroke_width: int = 2, opacity: float = 1.0,
          locked: bool = True) -> dict:
    attrs = {"x": x, "y": y, "innerRadius": inner_r, "outerRadius": outer_r,
             "fill": fill, "stroke": stroke, "strokeWidth": stroke_width}
    if opacity < 1.0:
        attrs["opacity"] = opacity
    return {"id": eid, "type": "ring", "locked": locked, "attrs": attrs}


# ── Shared Elements ────────────────────────────────────


def _footer_elements(brand: dict) -> list:
    accent = brand["palette"].get("accent", "#1565C0")
    bfont = brand["fonts"].get("body", DEFAULT_BFONT)
    return [
        _rect("accent-bar", 0, FOOTER_Y, W, FOOTER_H, accent),
        _image("web-logo", 60, FOOTER_Y + 10, 40, 40, "/assets/web-logo.png"),
        _text("web-url", 106, FOOTER_Y + 17, "www.nicdc.in", 26, bfont, "white", 300),
        _text("social-handle", 860, FOOTER_Y + 17, "@nicdc01", 26, bfont, "white", 200),
        _image("x-logo", 814, FOOTER_Y + 10, 40, 40, "/assets/x-logo.png"),
        _image("linkedin-logo", 758, FOOTER_Y + 10, 40, 40, "/assets/linkedin-logo.png"),
    ]


def _logo_elements(brand: dict, y: int = 8) -> list:
    """Build NICDC + DPIIT logo pair. Both share LOGO_WIDTH; heights are
    computed from the natural aspect ratio so neither logo is distorted."""
    logo_dims = _read_logo_dims()
    # Compute display height from natural ratio using the shared width
    def _h(eid: str) -> int:
        d = logo_dims.get(eid, {"width": 1, "height": 1})
        return round(LOGO_WIDTH * d["height"] / d["width"]) if d["width"] else LOGO_WIDTH
    return [
        _image("nicdc-logo", 940, y,
               LOGO_WIDTH, _h("nicdc-logo"),
               brand.get("logo", "/assets/nicdc-logo.png"), locked=True),
        _image("dpiit-logo", 860, y + 4,
               LOGO_WIDTH, _h("dpiit-logo"),
               brand.get("dpiit_logo", "/assets/dpiit-logo.png"), locked=True),
    ]


def _get_image_meta(images: list[dict], idx: int) -> tuple[str, int, int]:
    """Get (src, natural_width, natural_height) for image at index."""
    if idx < len(images):
        return images[idx]["src"], images[idx]["width"], images[idx]["height"]
    return "/assets/nicdc-logo.png", 1080, 1080


# ── Variation 1: Classic (Top-Down) ───────────────────


def _build_classic(content: dict, images: list[dict], brand: dict) -> dict:
    """Build a deterministic top-down layout with no overlapping elements."""
    palette = brand.get("palette", {})
    fonts = brand.get("fonts", {})
    primary = palette.get("primary", "#092240")
    accent = palette.get("accent", "#1565C0")
    highlight = palette.get("highlight", "#E65100")
    bg = palette.get("background", "#F3F7FA")
    hfont = fonts.get("heading", DEFAULT_HFONT)
    bfont = fonts.get("body", DEFAULT_BFONT)

    headline = content.get("headline", "")
    body = content.get("body", "")
    stat_number = content.get("stat_number", "")
    stat_label = content.get("stat_label", "")

    # ── Measure text heights ──
    headline_h = _estimate_text_height(headline, 40, CW, HEADLINE_LINE_H, hfont)
    body_h = _estimate_text_height(body, 24, CW, LINE_H, bfont)

    # ── Top-down: header + headline + accent line ──
    cat_tag_y = 18
    headline_y = 72
    accent_y = headline_y + headline_h + 10

    # ── Bottom-up: footer → stats → body → divider → subhead ──
    has_stats = bool(stat_number)
    if has_stats:
        stats_y = FOOTER_Y - STATS_GAP - STATS_H  # 910
    else:
        stats_y = FOOTER_Y - STATS_GAP

    body_y = stats_y - BODY_GAP - body_h
    divider_y = body_y - DIVIDER_GAP
    subhead_y = divider_y - SUBHEAD_GAP - 22

    # ── Overflow check: body vs subhead ──
    body_font_size = 24
    min_gap = IMG_GAP_BOT
    while body_y < subhead_y + 22 + min_gap and body_font_size > 16:
        body_font_size -= 2
        body_h = _estimate_text_height(body, body_font_size, CW, LINE_H, bfont)
        body_y = stats_y - BODY_GAP - body_h
        divider_y = body_y - DIVIDER_GAP
        subhead_y = divider_y - SUBHEAD_GAP - 22

    # ── Overflow check: body vs accent line ──
    while body_y < accent_y + IMG_GAP_TOP + 60 and body_font_size > 14:
        body_font_size -= 2
        body_h = _estimate_text_height(body, body_font_size, CW, LINE_H, bfont)
        body_y = stats_y - BODY_GAP - body_h
        divider_y = body_y - DIVIDER_GAP
        subhead_y = divider_y - SUBHEAD_GAP - 22

    # ── Image slot ──
    img_slot_top = accent_y + IMG_GAP_TOP
    img_slot_bot = subhead_y - IMG_GAP_BOT
    img_slot_h = max(img_slot_bot - img_slot_top, 60)

    img_src, img_nat_w, img_nat_h = _get_image_meta(images, 0)
    img_w, img_h = _fit_image(img_nat_w, img_nat_h, CW, img_slot_h)
    img_x = M + (CW - img_w) // 2
    img_y = img_slot_top + (img_slot_h - img_h) // 2

    # ── Build elements ──
    elements = [
        # Decorative background circles
        _circle("bg-deco-1", 920, 280, 240, accent, opacity=0.06),
        _circle("bg-deco-2", 100, 950, 180, primary, opacity=0.04),

        # Header
        _text("cat-tag", M, cat_tag_y,
              content.get("category", "NEWS").upper(), 14, bfont, accent, 200,
              font_style="bold"),
        *_logo_elements(brand),

        # Headline
        _text("headline", M, headline_y, headline, 40, hfont, primary, CW,
              font_style="bold", line_height=HEADLINE_LINE_H),

        # Accent line
        _line("accent-line", [M, accent_y, W - M, accent_y], accent, stroke_width=3),

        # Image
        _image("img-0", img_x, img_y, img_w, img_h, img_src, corner_radius=16),

        # Subhead
        _text("subhead", M, subhead_y, "KEY HIGHLIGHTS", 22, hfont, accent, 400,
              font_style="bold"),

        # Divider
        _line("divider", [M, divider_y, M + 300, divider_y], accent, stroke_width=2),

        # Body
        _text("body", M, body_y, body, body_font_size, bfont, primary, CW,
              line_height=LINE_H),
    ]

    # Stats (if present)
    if has_stats:
        elements.extend([
            _rect("stat-box", M, stats_y, 380, STATS_H, highlight,
                  corner_radius=14, opacity=0.1),
            _text("stat-num", M + 20, stats_y + 8, stat_number, 42, hfont,
                  highlight, 340, font_style="bold"),
            _text("stat-label", M + 20, stats_y + 55, stat_label, 16, bfont,
                  primary, 340),
        ])

    # Footer
    elements.extend(_footer_elements(brand))

    return {
        "canvas": {"width": W, "height": H, "background": bg},
        "elements": elements,
    }


# ── Variation 2: Split (Left-Right) ───────────────────


def _build_split(content: dict, images: list[dict], brand: dict) -> dict:
    """Build a deterministic split layout with no overlapping elements.

    The right-panel content (headline → subhead → body → stats) is
    computed bottom-up then shifted so the block centres vertically in
    the card, eliminating the large gap that previously appeared
    between the heading and the body.
    """
    palette = brand.get("palette", {})
    fonts = brand.get("fonts", {})
    primary = palette.get("primary", "#092240")
    accent = palette.get("accent", "#1565C0")
    highlight = palette.get("highlight", "#E65100")
    bg = palette.get("background", "#F3F7FA")
    hfont = fonts.get("heading", DEFAULT_HFONT)
    bfont = fonts.get("body", DEFAULT_BFONT)

    headline = content.get("headline", "")
    body = content.get("body", "")
    stat_number = content.get("stat_number", "")
    stat_label = content.get("stat_label", "")

    # ── Measure text heights ──
    headline_h = _estimate_text_height(headline, 34, RIGHT_CONTENT_W, HEADLINE_LINE_H, hfont)
    body_h = _estimate_text_height(body, 21, RIGHT_CONTENT_W, LINE_H, bfont)

    has_stats = bool(stat_number)
    stats_h = STATS_H if has_stats else 0

    # ── Fixed inter-element gaps ──
    GAP_HEADLINE_ACCENT  = 10   # accent line below headline
    GAP_ACCENT_SUBHEAD   = 20   # space from accent line to KEY HIGHLIGHTS
    GAP_SUBHEAD_DIVIDER  = 8    # divider directly below subhead
    GAP_DIVIDER_BODY     = 12   # body text starts below divider
    GAP_BODY_STATS       = 20   # gap between body and stat box

    # ── Total content height (bottom-up) ──
    content_h = (
        headline_h
        + GAP_HEADLINE_ACCENT
        + GAP_ACCENT_SUBHEAD
        + 18                          # subhead text height
        + GAP_SUBHEAD_DIVIDER
        + GAP_DIVIDER_BODY
        + body_h
        + GAP_BODY_STATS
        + stats_h
    )

    # ── Centre the block in the right card ──
    # Card usable area: y=30 (top padding) to y=960 (footer)
    CARD_TOP    = 30
    CARD_BOTTOM = FOOTER_Y          # 1020
    CARD_H      = CARD_BOTTOM - CARD_TOP  # 990
    offset      = max((CARD_H - content_h) // 2, 0)

    # ── Place elements top-down ──
    headline_y  = CARD_TOP + offset
    accent_y    = headline_y + headline_h + GAP_HEADLINE_ACCENT
    subhead_y   = accent_y  + GAP_ACCENT_SUBHEAD
    divider_y   = subhead_y + 18 + GAP_SUBHEAD_DIVIDER
    body_y      = divider_y + GAP_DIVIDER_BODY
    stats_y     = body_y + body_h + GAP_BODY_STATS

    # ── Left panel: image (aspect-ratio preserved) ──
    img_src, img_nat_w, img_nat_h = _get_image_meta(images, 0)
    img_w, img_h = _fit_image(img_nat_w, img_nat_h, IMG_SLOT_W, IMG_SLOT_MAX_H)
    img_x = IMG_PAD + (IMG_SLOT_W - img_w) // 2
    img_y = IMG_PAD + (IMG_SLOT_MAX_H - img_h) // 2

    # ── Logo dims ──
    logo_dims = _read_logo_dims()
    def _logo_h(eid: str) -> int:
        d = logo_dims.get(eid, {"width": 1, "height": 1})
        return round(LOGO_WIDTH * d["height"] / d["width"]) if d["width"] else LOGO_WIDTH

    # ── Build elements ──
    elements = [
        # Left panel
        _rect("left-panel", 0, 0, LEFT_W, H - FOOTER_H, primary),
        _image("img-0", img_x, img_y, img_w, img_h, img_src, corner_radius=16),
        _rect("left-accent", IMG_PAD, 700, IMG_SLOT_W, 6, accent, corner_radius=3),

        # Decorative ring on left
        _ring("deco-ring", 80, 80, 100, 120, fill="transparent",
              stroke=accent, stroke_width=2, opacity=0.08),

        # Right card
        _rect("right-card", RIGHT_X, 30, RIGHT_W, H - FOOTER_H - 30, "white",
              corner_radius=20, opacity=0.95),
        _rect("right-accent-bar", RIGHT_X, 30, 6, H - FOOTER_H - 30, accent,
              corner_radius=3),

        # Right content — header
        _text("cat-tag", RIGHT_CONTENT_X, headline_y - 32,
              content.get("category", "NEWS").upper(), 14, bfont, accent, 200,
              font_style="bold"),

        # Logos top-right
        _image("nicdc-logo", 940, 6,
               LOGO_WIDTH, _logo_h("nicdc-logo"),
               brand.get("logo", "/assets/nicdc-logo.png"), locked=True),
        _image("dpiit-logo", 860, 10,
               LOGO_WIDTH, _logo_h("dpiit-logo"),
               brand.get("dpiit_logo", "/assets/dpiit-logo.png"), locked=True),

        # Headline
        _text("headline", RIGHT_CONTENT_X, headline_y, headline, 34, hfont,
              primary, RIGHT_CONTENT_W, font_style="bold", line_height=HEADLINE_LINE_H),

        # Accent line
        _line("accent-line", [RIGHT_CONTENT_X, accent_y,
                              RIGHT_CONTENT_X + 250, accent_y], accent, stroke_width=3),

        # Subhead
        _text("subhead", RIGHT_CONTENT_X, subhead_y, "KEY HIGHLIGHTS", 18, hfont,
              accent, 300, font_style="bold"),

        # Divider
        _line("divider", [RIGHT_CONTENT_X, divider_y,
                           RIGHT_CONTENT_X + 200, divider_y], accent, stroke_width=2),

        # Body
        _text("body", RIGHT_CONTENT_X, body_y, body, 21, bfont,
              primary, RIGHT_CONTENT_W, line_height=LINE_H),
    ]

    # Stats (if present)
    if has_stats:
        elements.extend([
            _rect("stat-box", RIGHT_CONTENT_X, stats_y, RIGHT_CONTENT_W, STATS_H,
                  highlight, corner_radius=14, opacity=0.1),
            _text("stat-num", RIGHT_CONTENT_X + 20, stats_y + 8, stat_number, 38,
                  hfont, highlight, RIGHT_CONTENT_W - 40, font_style="bold"),
            _text("stat-label", RIGHT_CONTENT_X + 20, stats_y + 55, stat_label, 15,
                  bfont, primary, RIGHT_CONTENT_W - 40),
        ])

    # Footer
    elements.extend(_footer_elements(brand))

    return {
        "canvas": {"width": W, "height": H, "background": bg},
        "elements": elements,
    }


# ── Public API ─────────────────────────────────────────


def build_variation(
    variant: str,
    content: dict,
    images: list[dict],
    brand: dict,
) -> dict:
    """Build a complete Konva.js layout state for the given variant.

    Args:
        variant: "classic" or "split"
        content: {headline, body, stat_number, stat_label, category}
        images: [{src, width, height}, ...]
        brand: {palette, fonts, logo, dpiit_logo}

    Returns:
        Complete Konva.js state: {canvas: {...}, elements: [...]}
    """
    if variant == "split":
        return _build_split(content, images, brand)
    return _build_classic(content, images, brand)
