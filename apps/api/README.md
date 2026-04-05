# TextPulse API

FastAPI backend for TextPulse AI.

## Run locally
```powershell
python -m pip install -e .
copy .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

## Test
```powershell
pytest
```

## Migrations
```powershell
alembic upgrade head
```

## Worker
```powershell
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

## Cost-aware Claude modes
- `cheap`: prefers Haiku for live requests and synthesis
- `balanced`: prefers Haiku for bulk work and Sonnet for synthesis, Q&A, and reply coach
- `premium`: prefers Sonnet by default and can use Opus for high-value live work if `ANTHROPIC_ALLOW_OPUS=true`

The backend estimates request cost before each Claude call and automatically downgrades the model if the request would exceed the configured budget caps.

## Import processing
- Apple Messages imports can scan a `chat.db` upload, list likely direct-message contacts, and require a person selection before the import is confirmed.
- Uploads can be staged into a preview session first, then confirmed into a real import without re-uploading the file.
- Confirmed imports are accepted immediately and persisted before parsing begins.
- Large TXT, CSV, and WhatsApp-style files parse from disk to avoid reading the whole transcript into memory first.
- Telegram and Instagram JSON exports now support file-path parsing, and Android XML imports stream through `iterparse` for large archives.
- By default, file uploads process in FastAPI background tasks.
- For a more production-like setup, set `IMPORTS_USE_CELERY=true` and run Redis + the Celery worker so uploads are processed out of band.
- Celery workers retry failed import jobs with backoff, and the API exposes a manual retry endpoint for failed imports.
