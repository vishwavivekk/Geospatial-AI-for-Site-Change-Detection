# NICDC Social Studio

Social media post automation for NICDC with a **two-role approval workflow**:
editors design posts, approvers review them, and final approval publishes the
post to Instagram, X and LinkedIn automatically (mock APIs locally).

## Quick start (Windows)

```bash
# 1. Create the environment (once)
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt

# 2. Start the mock social media APIs (port 8100)
venv\Scripts\python -m uvicorn main:app --app-dir mock-apis --port 8100

# 3. Start the app (port 8000) — in a second terminal
venv\Scripts\python -m uvicorn app.main:app --port 8000 --reload
```

Open **http://localhost:8000** and sign in.

## Demo accounts

| Role     | Username   | Password      | What they can do |
|----------|------------|---------------|------------------|
| Editor   | `editor`   | `editor123`   | Add stories, design posts (canvas + AI), submit for approval, fix and resubmit |
| Approver | `approver` | `approver123` | Review designs, pin comments to elements, send back to editor, approve & publish |

Accounts live in `data/users.json` (auto-created on first run, passwords hashed).

## Workflow

```
Editor                          Approver
──────                          ────────
Add story
Design post (canvas / AI)
Send for approval ──────────▶   Review queue
                                Click elements + pin comments
        ◀──────────────────     Send back to editor (status: changes requested)
Fix design (feedback panel,
 "Fix with AI" per comment)
Resubmit (revision +1) ─────▶   Review again
                                Approve & publish
                                └─▶ auto-posts to Instagram, X, LinkedIn
```

- Every feedback round is archived per revision (`feedback_history`).
- On approval the review canvas is exported as a 1080×1080 PNG
  (`data/published/`), then published through the real multi-step API flows
  of each platform (IG container → publish, X media upload → tweet,
  LinkedIn image init → upload → post).
- Published post IDs are stored on the design and shown in both dashboards.
- Inspect published posts: http://localhost:8100/published

## Optional AI services

The approval workflow runs fully offline. Two AI features use external services:

| Feature | Service | Fallback when unavailable |
|---------|---------|---------------------------|
| Story embeddings (RAG) | llama.cpp on `LLAMA_CPP_URL` (default `http://localhost:8080`) | Deterministic hash embeddings — everything keeps working, retrieval quality reduced |
| "Generate with AI" layout + AI chat editing | OpenCode cloud API | Buttons show an error; design manually instead |

## Configuration (env vars)

| Variable | Default | Purpose |
|----------|---------|---------|
| `MOCK_API_BASE` | `http://localhost:8100` | Mock social media API server |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Base URL used for image links given to the APIs |
| `LLAMA_CPP_URL` | `http://localhost:8080` | Optional embedding server |

## Project layout

```
app/
  main.py           # FastAPI routes (pages + API), role guards
  auth.py           # Session-cookie login, editor/approver roles
  design_store.py   # Design lifecycle: pending → feedback → approved → published
  publisher.py      # Auto-publish to the three mock platforms
  pages/            # HTML pages (login, editor home, editor, review queue, review)
  ...               # RAG pipeline (loader, chunker, embedder, vector store)
mock-apis/main.py   # Mock Instagram / X / LinkedIn APIs (port 8100)
data/               # designs.json, users.json, images/, published/
```
