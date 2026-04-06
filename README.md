# TextPulse AI

**Upload your texts. Get a real read.**

TextPulse AI reads your actual conversation history — months or years of messages — and tells you what's really happening. Not horoscopes. Not personality quizzes. A specific, evidence-grounded analysis backed by direct quotes from the conversation, written by a frontier AI model that sees the full arc.

Built for anyone who's ever stared at a text thread and wondered *"what does this actually mean?"*

---

## How It Works

### 1. Import from iPhone (or anywhere)

Plug your iPhone into your computer, let iTunes make a local backup, then point TextPulse at the backup folder. The browser extracts only `chat.db` (~100-500 MB of text) from the multi-GB backup — your photos, videos, and everything else never leave your machine.

Also supports WhatsApp exports, Telegram JSON, Instagram DMs, Android SMS Backup, CSV/TXT transcripts, pasted text, and screenshot OCR.

### 2. Pick the person

TextPulse scans the Messages database and surfaces every one-to-one thread so you can choose exactly who you want to analyze. No need to know their phone number or email.

### 3. Get the read

The conversation is chunked into time windows and analyzed in two passes:

- **Window summaries** (fast, cheap model): what was the emotional tenor of each month? What shifted? What did each person seem to want?
- **Full synthesis** (strong model, sees everything): the actual relationship read — grounded in specific moments, direct quotes, and behavioral patterns across the full timeline.

The output is not generic. It references real things that were said, pinpoints when dynamics changed, and names what each person was doing — even when they weren't saying it directly.

### 4. Pay per read

Pricing scales with conversation depth, not a subscription:

| Tier | Messages | Price |
|------|----------|-------|
| Glance | Up to 2,500 | $9 |
| Read | 2,500 - 15,000 | $24 |
| Deep Read | 15,000 - 60,000 | $39 |
| Archive | 60,000 - 200,000 | $59 |
| Epic | 200,000+ | $89 |

A free scan (message stats, top topics, 3 teaser moments) runs before the paywall so you can see there's real signal before committing.

---

## What You Get

- **Key Takeaways** — 5 specific, grounded observations about the relationship
- **Personality Read** — who this person is based on how they actually text (not a keyword quiz)
- **Communication Style** — pacing, energy, reply patterns, who drives conversations
- **Emotional Landscape** — what triggers them, how they regulate, where the tension lives
- **Timeline Shifts** — the 3-4 moments where the dynamic changed, with quotes
- **Interest & Heat Signals** — grounded probability scores, not formulas
- **Relationship Receipt** — a shareable one-liner that captures their texting energy
- **Playbook** — communication cheat sheet, emotional playbook, conflict resolution, 2-week strategy
- **Reply Coach** — paste their latest message, get 3 response options with subtext analysis
- **Q&A** — ask specific questions about the conversation and get answers backed by real messages
- **Vault** — all messages tagged and browsable by category (flirty, vulnerable, red flags, etc.)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind CSS 4 |
| Backend | FastAPI, SQLAlchemy, Alembic |
| AI | Anthropic Claude (Haiku for bulk, Sonnet/Opus for synthesis) |
| Message Parsing | Native SQLite (iMessage chat.db), XML streaming (Android), JSON (Telegram/Instagram) |
| Client-Side Extraction | sql.js (WASM SQLite in browser for iTunes backup reading) |
| Background Jobs | Celery + Redis (optional; FastAPI background tasks for local dev) |
| Database | PostgreSQL + pgvector (production), SQLite (local dev) |
| Storage | Local disk or S3-compatible object storage |
| Auth | JWT with field-level AES-GCM encryption |

---

## Architecture

```
iPhone backup folder (5-50 GB on disk)
        |
        v
[Browser: sql.js reads Manifest.db, extracts only chat.db]
        |
        v  (~100-500 MB upload)
[FastAPI: parse iMessage SQLite, discover contacts]
        |
        v
[User picks the person]
        |
        v
[Background worker: persist messages, tag vault categories]
        |
        v
[Windowed reading pipeline]
   |-- Haiku: summarize each month (~$0.05/window)
   |-- Select 200 high-signal messages across full timeline
   |-- Sonnet/Opus: synthesize full read from summaries + messages
        |
        v
[Structured profile stored in DB]
        |
        v
[Frontend renders: profile, analytics, vault, Q&A, reply coach]
```

---

## Local Development

### Backend

```powershell
cd apps\api
python -m pip install -e .
copy .env.example .env
# Edit .env: set JWT_SECRET, ENCRYPTION_KEY, ANTHROPIC_API_KEY
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd apps\web
npm install
copy .env.example .env.local
# Edit .env.local: set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Docker Compose

```powershell
docker compose up --build
```

Brings up PostgreSQL (5432), Redis (6379), API (8000), and Web (3000).

---

## Environment Variables

### Backend (`apps/api/.env`)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL or SQLite connection string |
| `REDIS_URL` | Celery broker (optional for local dev) |
| `JWT_SECRET` | Long random secret for auth tokens |
| `ENCRYPTION_KEY` | Base64 urlsafe 32-byte key for field encryption |
| `ANTHROPIC_API_KEY` | Enables AI reading pipeline |
| `ANTHROPIC_DEFAULT_MODE` | `cheap`, `balanced`, or `premium` |
| `MAX_UPLOAD_SIZE_MB` | Upload cap (default 150) |
| `IMPORTS_USE_CELERY` | `true` to use Celery workers instead of background tasks |

### Frontend (`apps/web/.env.local`)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | API origin (e.g. `http://localhost:8000`) |

---

## Import Paths

| Source | Method | What to upload |
|--------|--------|---------------|
| **iPhone (Windows)** | iTunes backup folder via browser picker | TextPulse extracts chat.db client-side |
| **iPhone (Mac)** | Direct file | `~/Library/Messages/chat.db` |
| **WhatsApp** | In-app export | `.txt` or `.zip` |
| **Telegram** | Desktop export | `.json` |
| **Instagram** | Data download | Thread `.json` |
| **Android** | SMS Backup & Restore | `.xml` |
| **Any platform** | Paste or file | `.csv`, `.txt`, or paste directly |
| **Screenshots** | OCR | `.png`, `.jpg` |

---

## Project Structure

```
apps/
  api/                  # FastAPI backend
    app/
      api/routes/       # HTTP endpoints
      models/           # SQLAlchemy entities
      schemas/          # Pydantic models
      services/
        analysis_engine.py   # Windowed reading pipeline
        parsers/
          imessage.py        # Apple Messages parser
          ios_backup.py      # iTunes backup extraction
          whatsapp.py        # WhatsApp export parser
          telegram.py        # Telegram JSON parser
          ...
        llm.py               # Claude API routing + cost management
        reply_coach.py       # Real-time reply coaching
        qa.py                # Context-aware Q&A
    tests/
  web/                  # Next.js 16 frontend
    src/
      lib/
        ios-backup-extract.ts  # Client-side backup extraction (sql.js)
        api.ts                 # API client
      components/
        contact-workspace.tsx  # Main analysis UI
        dashboard-home.tsx     # Landing + import hub
docs/
  export-guides.md      # User-facing platform export instructions
  privacy.md            # Privacy and security notes
```

---

## Testing

```powershell
# Backend
cd apps\api
python -m pytest -x -q

# Frontend
cd apps\web
npm run lint
npx tsc --noEmit
```

---

## Deployment

- **Frontend**: Vercel or any Node host. Set `NEXT_PUBLIC_API_BASE_URL`.
- **Backend**: Render, Railway, Fly.io, or VPS. Back with PostgreSQL + Redis.
- **Workers**: `celery -A app.workers.celery_app.celery_app worker --loglevel=info`

---

## Roadmap

- [ ] Stripe Checkout integration for per-read payments
- [ ] Encrypted iTunes backup support (password-based Manifest.db decryption)
- [ ] Browser-side zip extraction for users who zipped their backup
- [ ] Streaming progress UI during windowed analysis
- [ ] Multi-contact comparison reads
- [ ] Group chat analysis
- [ ] Mobile-responsive import flow
- [ ] Shareable receipt cards (image export)

---

## License

Private. All rights reserved.
