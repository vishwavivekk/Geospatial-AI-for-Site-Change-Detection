import re
from sqlalchemy import select, delete
from app.models import Category


BRAND_TEMPLATES = {
    "authoritative": {
        "palette": {
            "primary": "#092240", "accent": "#1565C0", "highlight": "#E65100",
            "success": "#2E7D32", "background": "#F3F7FA",
        },
        "fonts": {"heading": "Georgia, serif", "body": "Inter, sans-serif"},
        "logo": "/assets/nicdc-logo.png",
        "dpiit_logo": "/assets/dpiit-logo.png",
        "tone": "authoritative, institutional, news-driven",
        "layout_instructions": "Clean, headline-driven layout. Large bold headline at top, source attribution at bottom. Minimal decorative elements. High contrast text on solid background. Keep text dense but scannable — bullet points or short paragraphs preferred.",
    },
    "celebratory": {
        "palette": {
            "primary": "#1A237E", "accent": "#F9A825", "highlight": "#E65100",
            "success": "#2E7D32", "background": "#FFF8E1",
        },
        "fonts": {"heading": "Georgia, serif", "body": "Inter, sans-serif"},
        "logo": "/assets/nicdc-logo.png",
        "dpiit_logo": "/assets/dpiit-logo.png",
        "tone": "celebratory, milestone-oriented, community-first",
        "layout_instructions": "Bold, vibrant layout with strong visual hierarchy. Feature event name and date prominently. Decorative elements at low opacity for energy. Can be denser — include date, time, venue in a structured block. Hero image should be prominent.",
    },
    "opportunity-driven": {
        "palette": {
            "primary": "#0D3B2E", "accent": "#2E7D32", "highlight": "#F9A825",
            "success": "#1B5E20", "background": "#F1F8E9",
        },
        "fonts": {"heading": "Georgia, serif", "body": "Inter, sans-serif"},
        "logo": "/assets/nicdc-logo.png",
        "dpiit_logo": "/assets/dpiit-logo.png",
        "tone": "opportunity-driven, growth-focused, welcoming",
        "layout_instructions": "Eye-catching, role-focused layout. Feature the job title or opportunity prominently in large text. Use accent shapes to draw attention to key details. Generous whitespace. Two-column or split layout works well.",
    },
}


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", name.lower().strip().replace(" ", "-"))


class CategoryRepo:
    def __init__(self, session):
        self.session = session

    async def list(self) -> list[dict]:
        result = await self.session.execute(select(Category).order_by(Category.name))
        return [row[0].to_dict() for row in result.all()]

    async def get(self, slug: str) -> dict | None:
        result = await self.session.execute(
            select(Category).where(Category.slug == slug)
        )
        cat = result.scalar_one_or_none()
        return cat.to_dict() if cat else None

    async def create(self, name: str, template: str, layout_instructions: str = "") -> dict:
        slug = _sanitize_name(name)
        if not slug:
            raise ValueError("Invalid category name")
        existing = await self.session.execute(
            select(Category).where(Category.slug == slug)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Category '{slug}' already exists")
        tmpl = BRAND_TEMPLATES.get(template)
        if not tmpl:
            raise ValueError(f"Unknown template '{template}'. Available: {', '.join(BRAND_TEMPLATES)}")
        cat = Category(
            slug=slug,
            name=name.strip().title(),
            palette=dict(tmpl["palette"]),
            fonts=dict(tmpl["fonts"]),
            logo=tmpl["logo"],
            dpiit_logo=tmpl.get("dpiit_logo", ""),
            tone=tmpl["tone"],
            layout_instructions=layout_instructions or tmpl.get("layout_instructions", ""),
        )
        self.session.add(cat)
        await self.session.commit()
        return cat.to_dict()

    async def update(self, slug: str, data: dict) -> dict:
        result = await self.session.execute(
            select(Category).where(Category.slug == slug)
        )
        cat = result.scalar_one_or_none()
        if not cat:
            raise ValueError(f"Category '{slug}' not found")
        for key in ("name", "palette", "fonts", "logo", "dpiit_logo", "tone", "layout_instructions"):
            if key in data:
                setattr(cat, key, data[key])
        await self.session.commit()
        return cat.to_dict()

    async def delete(self, slug: str) -> bool:
        result = await self.session.execute(
            select(Category).where(Category.slug == slug)
        )
        cat = result.scalar_one_or_none()
        if not cat:
            return False
        await self.session.delete(cat)
        await self.session.commit()
        return True

    @staticmethod
    def get_templates() -> "list[dict]":
        return [
            {"id": tid, "palette": t["palette"], "tone": t["tone"]}
            for tid, t in BRAND_TEMPLATES.items()
        ]
