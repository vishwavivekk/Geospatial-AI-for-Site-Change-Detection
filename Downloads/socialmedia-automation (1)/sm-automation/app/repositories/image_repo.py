from sqlalchemy import select, delete

from app.models import ImageFile


class ImageRepo:
    def __init__(self, session):
        self.session = session

    async def register(
        self, filename: str, original_filename: str | None = None,
        width: int | None = None, height: int | None = None,
        file_size: int | None = None,
    ) -> ImageFile:
        img = ImageFile(
            filename=filename,
            original_filename=original_filename,
            width=width,
            height=height,
            file_size=file_size,
        )
        self.session.add(img)
        await self.session.commit()
        await self.session.refresh(img)
        return img

    async def get(self, filename: str) -> ImageFile | None:
        result = await self.session.execute(
            select(ImageFile).where(ImageFile.filename == filename)
        )
        return result.scalar_one_or_none()

    async def delete(self, filename: str) -> bool:
        result = await self.session.execute(
            select(ImageFile).where(ImageFile.filename == filename)
        )
        img = result.scalar_one_or_none()
        if not img:
            return False
        await self.session.delete(img)
        await self.session.commit()
        return True
