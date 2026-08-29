from sqlalchemy import select, delete

from app.models import Chunk


class ChunkRepo:
    def __init__(self, session):
        self.session = session

    async def add_chunks(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self.session.add(chunk)
        await self.session.commit()

    async def get_by_story(self, story_id: str) -> list[Chunk]:
        result = await self.session.execute(
            select(Chunk).where(Chunk.story_id == story_id)
            .order_by(Chunk.chunk_index)
        )
        return [row[0] for row in result.all()]

    async def delete_by_story(self, story_id: str) -> None:
        await self.session.execute(
            delete(Chunk).where(Chunk.story_id == story_id)
        )
        await self.session.commit()

    async def get_all_metadata(self) -> list[dict]:
        result = await self.session.execute(
            select(Chunk).order_by(Chunk.chunk_index)
        )
        return [
            {"text": c[0].text, "metadata": c[0].metadata_json or {}}
            for c in result.all()
        ]

    async def count(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(select(func.count(Chunk.id)))
        return result.scalar() or 0
