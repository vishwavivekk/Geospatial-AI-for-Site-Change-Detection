# Ingestion Pipeline Architecture

## Overview

A multimodal ingestion pipeline that accepts **topic**, **information** (text), and **images** — storing all three as linked pairs in the vector database for retrieval-augmented post generation.

---

## Data Flow

```
User uploads:
  Topic: "PM Modi Kurnool Visit"
  Info:  "PM laid foundation for Rs 13,430Cr projects..."
  Images: [photo1.jpg, photo2.jpg]
          │
          ▼
  ┌──────────────────────────────────┐
  │  1. Validate file extensions     │  → reject unsupported types (400)
  │  2. Validate file sizes          │  → reject > 10 MB (400)
  │  3. Save images to disk          │  → data/images/{uuid}.{ext}
  │  4. Chunk the information text   │  → N text chunks with extra_meta
  │  5. Attach image paths + topic   │  → every chunk gets:
  │     to each chunk's metadata     │      images=["uuid1.jpg", ...]
  │                                 │      topic="PM Modi Kurnool..."
  │  6. Embed each chunk (llama.cpp) │  → 1536-dim vectors
  │  7. Store in vector DB           │  → persist vectors.npy + metadata.json
  │  8. On any step failure          │  → delete saved images, re-raise
  └──────────────────────────────────┘
```

---

## Chunk Metadata Structure

Every chunk in the vector store carries this metadata:

```json
{
  "text": "PM laid foundation stone for projects worth Rs 13,430 crore...",
  "metadata": {
    "type": "story",
    "topic": "PM Modi Kurnool Visit",
    "title": "PM Modi Kurnool Visit",
    "date": "2026-07-10",
    "source": "user-submitted",
    "images": ["a1b2c3d4.jpg", "e5f6g7h8.jpg"],
    "filepath": "user-submitted"
  }
}
```

- `type`: `"story"` for user-submitted content, `"document"` for PIB markdown files
- `topic`: the story topic provided at upload
- `images`: list of saved filenames in `data/images/`
- `date`: ISO date of ingestion

---

## New Files

| File | Purpose |
|---|---|
| `app/image_store.py` | Save uploaded images to `data/images/` with UUID filenames, validate extensions/sizes, clean up on failure, serve via path resolver |

---

## Modified Files

| File | Change |
|---|---|
| `app/config.py` | Add `IMAGES_DIR`, `ALLOWED_IMAGE_EXTENSIONS`, `MAX_IMAGE_SIZE_MB` |
| `app/chunker.py` | Add `extra_meta: dict \| None` parameter to `chunk_document()` — merged into each chunk's metadata; auto-sets `type: "story"` when `extra_meta` is present |
| `app/main.py` | Add `POST /ingest/story` (multipart: topic, information, images) + `GET /images/{filename}`; import `Document`, `save_images`, `get_image_path` |
| `app/generator.py` | Include `images: list[str]` in each source dict from retrieved chunks |
| `app/slide_generator.py` | Include `images: list[str]` in each source dict from retrieved chunks |
| `app/main.py` | `_generate_cards()` picks first image from top source and passes `image_url` to `render_post()`; shows `[img]` indicator next to sources with images |
| `requirements.txt` | Add `python-multipart>=0.0.18` |

---

## Directory Layout (after ingestion)

```
sm-automation/
├── data/
│   └── images/           ← uploaded images stored here
│       ├── a1b2c3d4.jpg
│       └── e5f6g7h8.jpg
├── vectors.npy           ← persisted embeddings
├── metadata.json         ← persisted chunk metadata
├── app/
│   ├── image_store.py    ← NEW: image save/validate/cleanup logic
│   └── ...
```

---

## API Endpoints

### `POST /ingest/story`

**Request:** `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `topic` | string (Form) | Story topic (used as title, searchable via RAG) |
| `information` | string (Form) | Full text content of the story |
| `images` | file(s) (File, default=[]) | One or more image files (optional) |

**Response:**

```json
{
  "status": "ok",
  "chunks": 12,
  "images_saved": 2,
  "topic": "PM Modi Kurnool Visit"
}
```

**Logic:**
1. Call `save_images(images)` — validates extension + size, saves to `data/images/{uuid}.ext`
2. Create a `Document` object with the information as body, `source="user-submitted"`
3. Chunk the document via `chunk_document(doc, extra_meta={"type": "story", "topic": topic, "images": filenames})`
4. Embed all chunks via llama.cpp `/v1/embeddings`
5. Add to vector store and persist
6. On any exception: call `delete_images(saved_filenames)` to clean up disk, then re-raise

### `GET /images/{filename}`

Serves stored image files from `data/images/`. Returns 404 if file not found.

---

## Integration with Post Generation

When `generate_post()` retrieves chunks via RAG, the returned sources include image paths:

```json
{
  "parsed": {
    "headline": "PM Modi Launches Rs 13,430 Cr Projects in Kurnool",
    "body": "...",
    "hashtags": ["#Kurnool", "#APDevelopment"]
  },
  "sources": [
    {
      "title": "PM Modi Kurnool Visit",
      "url": null,
      "images": ["a1b2c3d4.jpg"]
    }
  ]
}
```

The **recommendation frontend** (`_generate_cards()`) picks the first image from the top-ranked source and passes its URL as `/images/{filename}` to `render_post()`, which injects it into `base_design.html` (falling back to the placeholder `600x450` image when no image is available).

---

## No New Dependencies

- `python-multipart` added to `requirements.txt` (required by FastAPI's `UploadFile`)
- Image handling uses stdlib: `uuid`, `os`, `pathlib`
- File uploads use FastAPI's `UploadFile`

---

## Edge Cases

| Case | Behavior |
|---|---|
| No images uploaded | `save_images` returns `[]`; chunks stored with `images: []`; renderer shows placeholder |
| Invalid file extension | `save_images` raises `HTTPException(400)` with allowed types listed |
| File exceeds 10 MB | `save_images` raises `HTTPException(400)` with filename and size limit |
| Partial upload failure | `save_images` deletes any already-saved files in the batch before re-raising |
| Embedding/storing failure mid-ingest | `ingest_story` catches exception, calls `delete_images()`, re-raises |
| Image file not found on disk at render time | Browser shows broken image (future: check existence in renderer, fall back to placeholder) |
| Duplicate topics | Treated as separate stories — new chunks appended with new UUID image filenames (no dedup) |
| Re-ingest same story | Upload again — new chunks appended (no dedup, new UUIDs for images) |
| Missing `data/images/` dir | `save_images` creates it via `os.makedirs(IMAGES_DIR, exist_ok=True)` |
| `GET /images/{filename}` with invalid name | Returns `404 Image not found` |

---

## Implementation Order (completed)

1. `app/config.py` — add `IMAGES_DIR`, `ALLOWED_IMAGE_EXTENSIONS`, `MAX_IMAGE_SIZE_MB`
2. `mkdir -p data/images`
3. `app/image_store.py` — save, validate, cleanup, path resolution
4. `requirements.txt` — add `python-multipart`
5. `app/chunker.py` — add `extra_meta` parameter to `chunk_document()`
6. `app/main.py` — add `POST /ingest/story` + `GET /images/{filename}`; update imports
7. `app/generator.py` — include `images` in each source dict
8. `app/slide_generator.py` — same
9. `app/main.py` — `_generate_cards()` passes `image_url` from top source to `render_post()`
