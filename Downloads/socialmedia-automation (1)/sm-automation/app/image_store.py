import os
import uuid

from fastapi import UploadFile, HTTPException

from app.config import IMAGES_DIR, ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_MB


async def save_images(files: list[UploadFile]) -> list[str]:
    if not files or all(f.filename is None or f.filename == "" for f in files):
        return []

    os.makedirs(IMAGES_DIR, exist_ok=True)
    saved: list[str] = []

    try:
        for file in files:
            if not file.filename:
                continue

            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise HTTPException(
                    400,
                    f"Unsupported image type '{ext}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
                )

            content = await file.read()
            if len(content) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    400,
                    f"Image '{file.filename}' exceeds {MAX_IMAGE_SIZE_MB} MB",
                )

            fname = uuid.uuid4().hex + ext
            fpath = os.path.join(IMAGES_DIR, fname)
            with open(fpath, "wb") as f:
                f.write(content)
            saved.append(fname)
    except Exception:
        delete_images(saved)
        raise

    return saved


def delete_images(filenames: list[str]) -> None:
    for fname in filenames:
        fpath = os.path.join(IMAGES_DIR, fname)
        try:
            os.remove(fpath)
        except FileNotFoundError:
            pass


def get_image_path(filename: str) -> str:
    return os.path.join(IMAGES_DIR, filename)
