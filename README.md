# TextPulse AI

TextPulse AI is a full-stack relationship intelligence platform for importing long conversation histories, generating predictive profiles, browsing a categorized message vault, asking follow-up questions with context, and getting reply coaching in real time.

## What is in this repo
- [`apps/web`](/Users/mikef/OneDrive/Desktop/TexrPulse%20AI/apps/web): Next.js 16 frontend with a premium dashboard, auth UX, dossier workspace, analytics, vault browser, Q&A, reply coach, and demo-backed fallback mode.
- [`apps/api`](/Users/mikef/OneDrive/Desktop/TexrPulse%20AI/apps/api): FastAPI backend with auth, contact management, import parsing, heuristic profile generation, analytics, vault tagging, Q&A, reply coaching, storage abstraction, and Celery worker scaffolding.
- [`docs/export-guides.md`](/Users/mikef/OneDrive/Desktop/TexrPulse%20AI/docs/export-guides.md): user-facing export instructions by platform.
- [`docs/privacy.md`](/Users/mikef/OneDrive/Desktop/TexrPulse%20AI/docs/privacy.md): privacy and security implementation notes.

## Core product flows
- Create and manage contact intelligence profiles
- Import conversation data from iMessage, WhatsApp, Telegram, Instagram, Android XML, CSV/TXT, paste, and screenshots
- Scan an Apple Messages `chat.db` upload, surface likely people, and confirm the right iPhone thread before importing
- Generate a structured contact profile with message-backed examples
- Browse analytics and tagged vault categories
- Ask questions in an ongoing Q&A thread
- Paste a fresh incoming message into Reply Coach
- Run in demo mode when live credentials are not wired yet
- Use cost-aware Claude routing so bulk work stays cheap while synthesis and coaching stay high quality
- Upload large transcript files and track them through background processing states instead of blocking the UI
- Stage large uploads into a real preview-and-confirm flow before any import job is committed

## Local development

### 1. Backend
```powershell
cd "C:\Users\mikef\OneDrive\Desktop\TexrPulse AI\apps\api"
python -m pip install -e .
copy .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

Notes:
- Default local development uses SQLite if `DATABASE_URL` is not set.
- For production-style local development, point `DATABASE_URL` at PostgreSQL with pgvector enabled.
- OCR uses Tesseract when available.

### 2. Frontend
```powershell
cd "C:\Users\mikef\OneDrive\Desktop\TexrPulse AI\apps\web"
npm install
copy .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

If the API is unavailable, the frontend automatically falls back to a realistic demo-backed workspace so product review can still happen without blocking on infra.

## Docker Compose
```powershell
cd "C:\Users\mikef\OneDrive\Desktop\TexrPulse AI"
docker compose up --build
```

This brings up:
- `postgres` on `5432`
- `redis` on `6379`
- `api` on `8000`
- `web` on `3000`

## Backend environment variables
- `DATABASE_URL`: PostgreSQL or SQLite connection string
- `REDIS_URL`: Celery broker and result backend
- `WEB_ORIGIN`: frontend origin for CORS
- `JWT_SECRET`: long random secret for access tokens
- `ENCRYPTION_KEY`: base64 urlsafe 32-byte key for AES-GCM field encryption
- `ANTHROPIC_API_KEY`: optional; enables live Claude-backed Q&A and reply coaching
- `ANTHROPIC_MODEL`: optional single-model override if you want one Claude model for every task
- `ANTHROPIC_DEFAULT_MODE`: `cheap`, `balanced`, or `premium`
- `ANTHROPIC_MODEL_HAIKU`, `ANTHROPIC_MODEL_SONNET`, `ANTHROPIC_MODEL_OPUS`: task-specific Claude model defaults
- `ANTHROPIC_ALLOW_OPUS`: set `true` only if you want premium mode to use Opus when the request stays within budget
- `ANTHROPIC_BULK_REQUEST_BUDGET_USD`, `ANTHROPIC_LIVE_REQUEST_BUDGET_USD`, `ANTHROPIC_PROFILE_REQUEST_BUDGET_USD`: estimated per-request budget caps that automatically downgrade model selection when needed
- `IMPORTS_USE_CELERY`: set `true` to send uploaded imports through Celery workers instead of FastAPI background tasks
- `MAX_UPLOAD_SIZE_MB`: max accepted upload size before the API rejects the file
- `IMPORT_PREVIEW_TTL_HOURS`: how long staged preview files stay valid before they are cleaned up
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL`: optional object storage configuration
- `OCR_ENABLED`: set `false` if OCR should be disabled

## Deployment notes

### Frontend
- Deploy [`apps/web`](/Users/mikef/OneDrive/Desktop/TexrPulse%20AI/apps/web) to Vercel or another Node-compatible host.
- Set `NEXT_PUBLIC_API_BASE_URL` to the public API origin.

### Backend
- Deploy [`apps/api`](/Users/mikef/OneDrive/Desktop/TexrPulse%20AI/apps/api) to Render, Railway, Fly.io, or a VPS.
- Back the API with PostgreSQL and Redis.
- Add HTTPS and private object storage before launch.

### Workers
- Run Celery with:
```powershell
cd "C:\Users\mikef\OneDrive\Desktop\TexrPulse AI\apps\api"
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

### Large-file import behavior
- Apple Messages imports now support an iPhone-first path: upload `chat.db`, review suggested contacts, then confirm the person to import.
- File uploads can be staged into a preview first, then confirmed without uploading the same file twice again.
- Confirmed imports are persisted immediately and then processed in the background.
- The frontend shows transfer progress first, then polls the persisted import status until parsing completes, retries, or fails.
- Generic TXT, CSV, and WhatsApp-style exports now parse from disk instead of loading the full file into memory first.
- Telegram and Instagram JSON exports now support file-based parsing, and Android XML imports use streaming `iterparse` for large archives.
- For local development, imports use FastAPI background tasks by default. For a more production-like setup, enable `IMPORTS_USE_CELERY=true` and run Redis + a Celery worker.
- Celery workers automatically retry failed import jobs with backoff, and failed imports can be manually retried from the workspace.

## Verification completed in this workspace
- Frontend lint: `npm run lint`
- Frontend production build: `npm run build`
- Backend syntax compile: `python -m compileall apps\api\app`
- Backend import smoke: `python -c "from app.main import app; print(app.title)"`
- Backend HTTP smoke: health endpoint returns `200`
- Backend auth/contact smoke: register -> create contact -> list contacts -> fetch contact

## Known live setup requirements
- Real Anthropic credentials for live model responses
- Final decision on Claude operating mode and per-request spend caps
- Final production `JWT_SECRET` and `ENCRYPTION_KEY`
- Production database and Redis
- Object storage credentials if uploads should persist outside local disk
- Final legal copy and privacy policy
