# TextPulse AI

**Upload your texts. Get a real read.**

TextPulse AI reads your actual conversation history — months or years of messages — and tells you what's really happening. Not horoscopes. Not personality quizzes. A specific, evidence-grounded analysis backed by computed behavioral data and direct quotes from the conversation, written by a frontier AI model that sees the full arc.

Built for anyone who's ever stared at a text thread and wondered *"what does this actually mean?"*

---

## Why This Is Different From Pasting Into ChatGPT

You can't paste 50,000 messages into a chatbot. Even if you could, a chatbot doesn't have timestamps, response-time deltas, session boundaries, or the ability to compare across relationships. TextPulse does.

| What you want to know | Pasting into Claude/ChatGPT | TextPulse |
|---|---|---|
| "Is this one-sided?" | Vibes from a snippet | Investment Asymmetry Score computed from 6 independent metrics |
| "Are they losing interest?" | Guess from recent texts | Fade Detector comparing last 30 days to prior 30 on 5 behavioral signals |
| "Will they ghost me?" | Generic advice | Ghost Risk Score from trailing response-time regression + initiation drop-off |
| "How does she compare to her?" | Impossible | Cross-contact compatibility analysis (timing, pacing, effort, topics) |
| "What changed and when?" | Can't see the full arc | Windowed month-by-month reading across the entire history |
| "What's their texting personality?" | Surface-level from a few messages | Behavioral fingerprint: double-text frequency, emotional vocabulary breadth, late-night ratio, plan-making patterns |

---

## How It Works

### 1. Import from iPhone (or anywhere)

Plug your iPhone into your computer, let iTunes make a local backup, then point TextPulse at the backup folder. The browser reads only `Manifest.db` and extracts `chat.db` (~100-500 MB of text) — your photos, videos, and the rest of the multi-GB backup never leave your machine and are never uploaded.

Also supports WhatsApp exports, Telegram JSON, Instagram DMs, Android SMS Backup, CSV/TXT transcripts, pasted text, and screenshot OCR.

### 2. Pick the person

TextPulse scans the Messages database and surfaces every one-to-one thread so you can choose exactly who you want to analyze. No need to know their phone number or email.

### 3. Free scan (before you pay)

Before the paywall, you get a free behavioral snapshot:
- Total message count, date range, conversation velocity
- Top topics and 3 AI-generated "moments I noticed" teasers
- Investment Asymmetry score, Ghost Risk, Fade Detection, Worth Your Time verdict
- Your pricing tier and exact price

This costs us ~$0.30 and gives you enough to know there's real signal before committing.

### 4. Pay per read

One-time payment per relationship. Not a subscription.

| Tier | Messages | Price |
|------|----------|-------|
| Glance | Up to 2,500 | $9 |
| Read | 2,500 - 15,000 | **$24** |
| Deep Read | 15,000 - 60,000 | **$39** |
| Archive | 60,000 - 200,000 | $59 |
| Epic | 200,000+ | $89 |

Stripe Checkout handles payment. Analysis only runs after successful payment.

### 5. Get the full read

The conversation is chunked into time windows and analyzed in three layers:

1. **Behavioral Intelligence** (computed, no AI) — response time distributions, double-text patterns, initiation trends, emotional vocabulary breadth, gap analysis, plan-making ratios. Ground truth from structured data.

2. **Window Summaries** (fast model) — what was the emotional tenor of each month? What shifted? What did each person seem to want? Direct quotes from each period.

3. **Full Synthesis** (strong model) — the actual relationship read, grounded in both the behavioral data and the window summaries. References specific moments, pinpoints when dynamics changed, and produces an actionable playbook.

Analysis runs asynchronously in the background. The frontend polls for progress and shows the result when complete.

---

## What You Get

### Behavioral Fingerprint (computed, not guessed)

| Metric | What it measures |
|--------|-----------------|
| Response time distribution | Full curve: % under 5min, 5-30min, 30min-2hr, 2-8hr, 8hr+ |
| Double-text frequency | Who sends 2+ messages before a reply, and how often |
| Initiation trend | Monthly plot: are they reaching out more or less over time? |
| Message length asymmetry | Ratio of their avg length to yours, trended monthly |
| Question-to-statement ratio | How curious/engaged vs. declarative |
| Emotional vocabulary breadth | Unique emotional words / sqrt(total words) |
| Late-night ratio | % of messages after 10pm |
| Plan-making ratio | Concrete plans vs. vague "we should" |
| Gap patterns | Median gap between conversations, who breaks silence |
| Conversation velocity | Messages per active day |

### Predictive Signals

| Signal | How it works |
|--------|-------------|
| **Investment Asymmetry** (-100 to +100) | Composite of initiation ratio, message length ratio, response speed, question ratio, double-text rate, silence-breaking. Negative = you're carrying it. |
| **Ghost Risk** (0-99%) | Trailing response-time trend + initiation drop-off + message shortening + investment asymmetry. With specific risk factors listed. |
| **Fade Detector** | Compares last 30 days to prior 30 on 5 key metrics. Flags if 3+ are declining simultaneously. |
| **Worth Your Time** | Plain-English verdict combining asymmetry score + trend direction. |

### AI Relationship Read

- **Key Takeaways** — 5 specific, evidence-grounded observations with direct quotes
- **Personality Read** — who this person is based on how they actually text across months/years
- **Communication Style** — pacing, energy, reply patterns, who drives conversations
- **Emotional Landscape** — what triggers them, how they regulate, where the tension lives
- **Timeline Shifts** — the 3-4 moments where the dynamic visibly changed, with quotes
- **Relationship Receipt** — shareable one-liner that captures their texting energy
- **Playbook** — communication cheat sheet, emotional playbook, conflict resolution, 2-week strategy

### Additional Features

- **Reply Coach** — paste their latest message, get 3 response options with subtext analysis, danger zones, and timing recommendations
- **Q&A** — ask specific questions about the conversation and get answers backed by real messages with citations
- **Vault** — all messages auto-tagged and browsable by category (flirty, vulnerable, red flags, plans, apologies, etc.)
- **Contact Comparison** — compare two imported contacts on timing compatibility, pacing, effort balance, topic overlap

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind CSS 4 |
| Backend | FastAPI, SQLAlchemy, Alembic |
| AI | Anthropic Claude (Haiku for window summaries, Sonnet/Opus for synthesis) |
| Behavioral Intelligence | Pure Python computation from structured message data |
| Message Parsing | Native SQLite (iMessage chat.db), XML streaming (Android), JSON (Telegram/Instagram) |
| Client-Side Extraction | sql.js (WASM SQLite in browser for iTunes backup reading) |
| Payments | Stripe Checkout (one-time per-read charges) |
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
[FREE SCAN: behavioral fingerprint + teaser moments + pricing tier]
        |
        v
[PAYWALL: Stripe Checkout → webhook confirms payment]
        |
        v
[PAID ANALYSIS (async background job)]
   |-- Behavioral Intelligence: 10+ computed metrics from structured data
   |-- Haiku: summarize each month (~$0.05/window)
   |-- Select 200 high-signal messages across full timeline
   |-- Sonnet/Opus: synthesize full read from behavioral data + summaries + messages
        |
        v
[Structured profile stored in DB]
        |
        v
[Frontend renders: profile, behavioral dashboard, analytics, vault, Q&A, reply coach]
```

---

## Local Development

### Backend

```powershell
cd apps\api
python -m pip install -e .
copy .env.example .env
# Edit .env: set JWT_SECRET, ENCRYPTION_KEY, ANTHROPIC_API_KEY
# Optional: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
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
| `MAX_UPLOAD_SIZE_MB` | Upload cap (default 500) |
| `STRIPE_SECRET_KEY` | Stripe secret key for payments |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
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

## API Endpoints

### Core Flow
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/contacts/{id}/analysis/scan` | Free behavioral scan + teaser (pre-paywall) |
| `POST` | `/contacts/{id}/analysis/checkout` | Create Stripe Checkout Session |
| `POST` | `/contacts/stripe/webhook` | Stripe payment webhook |
| `POST` | `/contacts/{id}/analysis/regenerate` | Queue full analysis (async, returns 202) |
| `GET` | `/contacts/{id}/analysis/status` | Poll analysis progress |
| `GET` | `/contacts/compare?contact_a=X&contact_b=Y` | Compare two contacts |

### Import
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/contacts/{id}/imports/preview` | Stage file + preview |
| `POST` | `/contacts/{id}/imports/confirm` | Confirm staged import |
| `POST` | `/contacts/{id}/imports/upload` | Direct upload |
| `POST` | `/contacts/{id}/imports/paste` | Paste transcript |

### Intelligence
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/contacts/{id}/reply-coach` | Get reply options for incoming message |
| `POST` | `/contacts/{id}/qa/sessions` | Create Q&A session |
| `POST` | `/contacts/{id}/qa/sessions/{sid}/messages` | Ask a question |

---

## Project Structure

```
apps/
  api/                  # FastAPI backend
    app/
      api/routes/
        analysis.py          # Async analysis + scan + status polling
        billing.py           # Stripe Checkout + webhook
        compare.py           # Cross-contact comparison
        imports.py           # File upload + preview + confirm
        reply_coach.py       # Real-time reply coaching
        qa.py                # Context-aware Q&A
      models/entities.py     # SQLAlchemy models
      schemas/contacts.py    # Pydantic schemas
      services/
        behavioral_intel.py  # THE MOAT: ground-truth behavioral fingerprint
        analysis_engine.py   # Windowed reading pipeline + synthesis
        parsers/
          imessage.py        # Apple Messages parser
          ios_backup.py      # iTunes backup extraction
        llm.py               # Claude API routing + cost management
        reply_coach.py       # Reply coaching logic
        qa.py                # Q&A with message retrieval
    tests/
  web/                  # Next.js 16 frontend
    src/
      lib/
        ios-backup-extract.ts  # Client-side backup extraction (sql.js)
        api.ts                 # API client with scan, checkout, polling
      components/
        contact-workspace.tsx  # Main analysis UI + async polling
        dashboard-home.tsx     # Landing + import hub
docs/
  export-guides.md
  privacy.md
```

---

## Testing

```powershell
# Backend (16 tests)
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
- **Stripe**: Set `STRIPE_SECRET_KEY` and configure webhook URL to `https://yourdomain.com/api/contacts/stripe/webhook`.
- **Workers**: `celery -A app.workers.celery_app.celery_app worker --loglevel=info`

---

## Roadmap

- [ ] Encrypted iTunes backup support (password-based Manifest.db decryption)
- [ ] Scan results rendered in frontend paywall UI
- [ ] Behavioral dashboard visualization (charts for trends)
- [ ] Streaming progress UI during windowed analysis
- [ ] Password reset flow
- [ ] Email verification on signup
- [ ] Rate limiting on auth + analysis endpoints
- [ ] Multi-contact comparison UI
- [ ] Group chat analysis
- [ ] Shareable receipt cards (image export)
- [ ] Mobile app wrapper

---

## License

Private. All rights reserved.
