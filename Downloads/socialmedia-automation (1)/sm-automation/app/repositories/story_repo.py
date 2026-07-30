from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.models import Story, StoryImage, Chunk


class StoryRepo:
    def __init__(self, session):
        self.session = session

    async def list_stories(self) -> list[dict]:
        result = await self.session.execute(
            select(Story)
            .options(selectinload(Story.story_images), selectinload(Story.chunks))
            .order_by(Story.created_at.desc())
        )
        stories = []
        for row in result.all():
            story = row[0]
            text_parts = [c.text for c in story.chunks]
            images = [si.filename for si in story.story_images]
            stories.append({
                "topic": story.topic,
                "title": story.title,
                "date": story.date or "",
                "category": story.category_name or "",
                "images": images,
                "text": "\n\n".join(text_parts),
                "chunks": len(story.chunks),
            })
        return stories

    async def get_story(self, topic: str) -> dict | None:
        result = await self.session.execute(
            select(Story)
            .where(Story.topic == topic)
            .options(selectinload(Story.story_images), selectinload(Story.chunks))
        )
        story = result.scalar_one_or_none()
        if not story:
            return None
        text_parts = [c.text for c in story.chunks]
        images = [si.filename for si in story.story_images]
        return {
            "topic": story.topic,
            "title": story.title,
            "date": story.date or "",
            "category": story.category_name or "",
            "images": images,
            "text": "\n\n".join(text_parts),
            "chunks": len(story.chunks),
        }

    async def get_story_orm(self, topic: str) -> Story | None:
        result = await self.session.execute(
            select(Story)
            .where(Story.topic == topic)
            .options(selectinload(Story.story_images), selectinload(Story.chunks))
        )
        return result.scalar_one_or_none()

    async def create_story(
        self, topic: str, title: str, date: str | None = None,
        source: str | None = None, prid: str | None = None,
        url: str | None = None, body_text: str = "",
        category_name: str | None = None, image_filenames: list[str] | None = None,
    ) -> Story:
        story = Story(
            topic=topic,
            title=title,
            date=date,
            source=source,
            prid=prid,
            url=url,
            body_text=body_text,
            category_name=category_name,
        )
        if image_filenames:
            story.story_images = [
                StoryImage(filename=f, original_filename=f)
                for f in image_filenames
            ]
        self.session.add(story)
        await self.session.commit()
        await self.session.refresh(story)
        return story

    async def delete_story(self, topic: str) -> list[str]:
        result = await self.session.execute(
            select(Story)
            .where(Story.topic == topic)
            .options(selectinload(Story.story_images))
        )
        story = result.scalar_one_or_none()
        if not story:
            return []
        images = [si.filename for si in story.story_images]
        await self.session.delete(story)
        await self.session.commit()
        return images
