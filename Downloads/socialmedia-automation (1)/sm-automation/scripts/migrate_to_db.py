"""
One-time migration script: JSON files + vectors.npy + metadata.json → SQLite.

Run from project root:  python scripts/migrate_to_db.py
"""

import json
import os
import sys
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _dt(value):
    """Parse an ISO timestamp string to a naive-UTC datetime (or None)."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        return None

from sqlalchemy import select
from app.database import async_session, engine, Base, DATABASE_PATH
from app.models import Category, Story, StoryImage, Chunk, Design, DesignComment, ImageFile
from app.config import BASE_DIR, VECTORS_PATH, METADATA_PATH
from app.chunker import Chunk as ChunkData
from app.vector_store import store as vector_store
from app.repositories.category_repo import _sanitize_name, BRAND_TEMPLATES

BRANDS_DIR = os.path.join(BASE_DIR, "data", "brands")
DESIGNS_PATH = os.path.join(BASE_DIR, "data", "designs.json")
IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")


def _rel(path: str) -> str:
    """Convert absolute path to relative (strip BASE_DIR prefix)."""
    if path and path.startswith(BASE_DIR):
        return path[len(BASE_DIR) + 1:]
    return path


async def migrate_categories():
    """Seed the default categories from brand templates (the legacy
    data/brands/*.json files use an older format, so the canonical
    template definitions are used instead)."""
    print("Seeding categories...")
    seeds = [
        ("News", "authoritative"),
        ("Events", "celebratory"),
        ("Hiring", "opportunity-driven"),
    ]
    count = 0
    async with async_session() as session:
        for name, template in seeds:
            slug = _sanitize_name(name)
            existing = await session.execute(
                select(Category).where(Category.slug == slug)
            )
            if existing.scalar_one_or_none():
                print(f"  Skipping existing category: {slug}")
                continue
            tmpl = BRAND_TEMPLATES[template]
            cat = Category(
                slug=slug,
                name=name,
                palette=dict(tmpl["palette"]),
                fonts=dict(tmpl["fonts"]),
                logo=tmpl["logo"],
                dpiit_logo=tmpl.get("dpiit_logo", ""),
                tone=tmpl["tone"],
                layout_instructions=tmpl.get("layout_instructions", ""),
            )
            session.add(cat)
            count += 1
        await session.commit()
    print(f"  Seeded {count} categories")


async def migrate_stories_and_chunks():
    print("Migrating stories and chunks...")
    if not os.path.isfile(METADATA_PATH):
        print("  No metadata.json found, skipping")
        return

    with open(METADATA_PATH) as f:
        meta_list = json.load(f)

    if not meta_list:
        print("  Empty metadata.json, skipping")
        return

    from collections import OrderedDict
    story_chunks: dict[str, list[dict]] = OrderedDict()

    for item in meta_list:
        m = item["metadata"]
        topic = m.get("topic", m.get("title", ""))
        if not topic:
            continue
        story_chunks.setdefault(topic, []).append(item)

    async with async_session() as session:
        for topic, items in story_chunks.items():
            existing = await session.execute(
                select(Story).where(Story.topic == topic)
            )
            if existing.scalar_one_or_none():
                print(f"  Skipping existing story: {topic[:60]}...")
                continue

            first = items[0]["metadata"]
            all_text = "\n\n".join(it["text"] for it in items)
            images = first.get("images", [])

            story = Story(
                topic=topic,
                title=first.get("title", topic),
                date=first.get("date", ""),
                source=first.get("source", ""),
                prid=first.get("prid"),
                url=first.get("url"),
                body_text=all_text,
                category_name=first.get("category", ""),
            )
            story.story_images = [
                StoryImage(filename=img, original_filename=img)
                for img in images
            ]
            session.add(story)
            await session.flush()

            for idx, item in enumerate(items):
                chunk = Chunk(
                    story_id=story.id,
                    text=item["text"],
                    chunk_index=idx,
                    metadata_json=item.get("metadata"),
                )
                session.add(chunk)

            print(f"  Story '{topic[:60]}...' with {len(items)} chunks")

        await session.commit()
    print(f"  Migrated {len(story_chunks)} stories")


async def migrate_designs():
    print("Migrating designs...")
    if not os.path.isfile(DESIGNS_PATH):
        print("  No designs.json found, skipping")
        return

    with open(DESIGNS_PATH) as f:
        designs_list = json.load(f)

    if not designs_list:
        print("  Empty designs.json, skipping")
        return

    async with async_session() as session:
        design_count = 0
        comment_count = 0
        for item in designs_list:
            existing = await session.execute(
                select(Design).where(Design.id == item["id"])
            )
            if existing.scalar_one_or_none():
                print(f"  Skipping existing design: {item['id']}")
                continue

            # Find story_id by topic
            story = await session.execute(
                select(Story).where(Story.topic == item["topic"])
            )
            story_row = story.scalar_one_or_none()
            story_id = story_row.id if story_row else None

            design_png = _rel(item.get("design_png", ""))
            comments_data = item.pop("comments", [])

            design = Design(
                id=item["id"],
                story_id=story_id,
                topic=item["topic"],
                category=item.get("category") or None,
                story_text=item.get("story_text", ""),
                story_images=item.get("story_images") or None,
                design_state=item["design_state"],
                design_png=design_png or None,
                variant_group=item.get("variant_group") or None,
                variant_index=item.get("variant_index", 0),
                status=item.get("status", "pending"),
                revision=item.get("revision", 1),
                submitted_by=item.get("submitted_by") or None,
                reviewed_by=item.get("reviewed_by") or None,
                reviewer_note=item.get("reviewer_note") or None,
                feedback_history=item.get("feedback_history") or None,
                post_results=item.get("publish_results") or item.get("post_results"),
                published_image_url=item.get("published_image_url") or None,
            )
            if _dt(item.get("submitted_at")):
                design.submitted_at = _dt(item.get("submitted_at"))
            design.reviewed_at = _dt(item.get("reviewed_at"))
            design.published_at = _dt(item.get("published_at"))
            session.add(design)
            await session.flush()

            for c in comments_data:
                comment = DesignComment(
                    id=c.get("id"),
                    design_id=design.id,
                    element_id=c.get("element_id"),
                    element_type=c.get("element_type"),
                    text=c["text"],
                    author=c.get("author") or None,
                )
                if _dt(c.get("created_at")):
                    comment.created_at = _dt(c.get("created_at"))
                session.add(comment)
                comment_count += 1
            design_count += 1

        await session.commit()
    print(f"  Migrated {design_count} designs with {comment_count} comments")


async def migrate_images():
    print("Migrating image metadata...")
    if not os.path.isdir(IMAGES_DIR):
        print("  No images directory, skipping")
        return

    async with async_session() as session:
        count = 0
        for fname in os.listdir(IMAGES_DIR):
            fpath = os.path.join(IMAGES_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            existing = await session.execute(
                select(ImageFile).where(ImageFile.filename == fname)
            )
            if existing.scalar_one_or_none():
                continue
            fsize = os.path.getsize(fpath)
            img = ImageFile(
                filename=fname,
                original_filename=fname,
                file_size=fsize,
            )
            session.add(img)
            count += 1
        await session.commit()
    print(f"  Registered {count} image files")


async def migrate_vector_store():
    """Ensure vectors.npy still loads with DB-backed chunks."""
    print("Verifying vector store integration...")
    if not os.path.isfile(VECTORS_PATH):
        print("  No vectors.npy found, skipping")
        return

    from app.vector_store import store
    loaded = store.load()
    if loaded:
        print(f"  Vector store loaded: {store.size} chunks")
    else:
        print("  Vector store not loaded (no data yet)")


async def main():
    print(f"Migrating data to: {DATABASE_PATH}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")

    await migrate_categories()
    await migrate_stories_and_chunks()
    await migrate_designs()
    await migrate_images()
    await migrate_vector_store()

    print("\nMigration complete.")
    print("  - metadata.json can now be archived")
    print("  - data/designs.json can now be archived")
    print("  - vectors.npy is still used (keep it)")


if __name__ == "__main__":
    asyncio.run(main())
