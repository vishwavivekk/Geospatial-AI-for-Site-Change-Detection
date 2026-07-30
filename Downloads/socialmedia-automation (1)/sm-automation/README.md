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

- "Generate with AI" produces **two layout variations** (deterministic layout
  engine + LLM copywriting + LLM color enhancement); the editor compares them
  with tabs and both are submitted for review.
- Every feedback round is archived per revision (`feedback_history`).
- The approver edits the **caption** in the approve dialog; on approval the
  stored design PNG is posted.
- **Publishing modes** (`SOCIAL_MODE` env):
  - `real` — posts to the Instagram/LinkedIn accounts connected in the
    Zernio dashboard (post URLs stored on the design).
  - `mock` (default) — simulates the platform APIs locally
    (inspect at http://localhost:8100/published). Real mode falls back to
    mock automatically if posting fails.
- **Categories are dynamic**: editors manage them in the dashboard
  (name + brand template + layout instructions); each carries the palette,
  fonts, and logos used by AI generation.
- Data lives in SQLite (`data/sm-automation.db`); embeddings stay in
  `vectors.npy`. To migrate older JSON data: `python scripts/migrate_to_db.py`.
- `template-creation/` is a standalone tool (port 8770) for turning layered
  PSD exports into fillable templates: `python template-creation/server.py`.

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
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Fallback base URL for image links given to the APIs |
| `ZERNIO_API_KEY` | *(empty)* | Zernio API key — used for media hosting and (in real mode) posting to connected social accounts. Set it in `.env` (never committed). |
| `SOCIAL_MODE` | `mock` | `real` posts to the social accounts connected in Zernio when a design is approved. Keep `mock` on dev machines. |
| `LLAMA_CPP_URL` | `http://localhost:8080` | Optional embedding server |

## Deploy to a server (GCP VM / any Debian or Ubuntu box)

One command from this machine (needs SSH access to the server):

```bash
powershell -File deploy/deploy.ps1 -ServerIp YOUR_VM_IP -User YOUR_SSH_USER
```

This packs the project (secrets excluded), uploads it, and runs
`deploy/setup-server.sh` on the VM, which installs Python + nginx, creates the
venv, and starts both apps as systemd services (`sm-studio`, `sm-mock-apis`)
behind nginx on port 80. The mock API inspector is proxied at `/mock/published`.

Requirements on the GCP side: a firewall rule allowing HTTP (port 80) — tick
"Allow HTTP traffic" on the VM or add the `default-allow-http` tag.
After deploying, change the demo passwords in `/opt/sm-automation/data/users.json`.

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
