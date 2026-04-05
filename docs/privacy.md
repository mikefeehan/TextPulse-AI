# TextPulse AI Privacy & Security Notes

## What the app stores
- Account email and password hash
- Contact records and relationship metadata
- Imported message history, timestamps, and derived analytics
- AI-generated profiles, vault tags, highlights, and coaching sessions
- Uploaded source files when local or S3-backed storage is enabled

## Security posture in this codebase
- Conversation text and profile JSON are encrypted at rest in the application layer before persistence.
- Passwords are stored as salted PBKDF2-SHA256 hashes.
- API requests are designed for HTTPS-only deployment.
- Data access is scoped per authenticated user.
- Contact deletion is implemented as a hard delete through relational cascade behavior.
- Demo mode never sends data to an external model provider.

## What still requires production configuration
- A strong `JWT_SECRET`
- A unique 32-byte `ENCRYPTION_KEY`
- HTTPS termination at the hosting layer
- Production database backups and retention policies
- Vendor-level data retention settings for Anthropic and storage providers
- A final public-facing privacy policy and terms of use reviewed by counsel

## Recommended next production steps
1. Run the API behind HTTPS with secure headers and trusted proxy configuration.
2. Move uploads to private S3 buckets with lifecycle rules and server-side encryption.
3. Add audit logging for destructive actions like account delete and contact delete.
4. Add real session expiry enforcement and optional 2FA.
5. Run a security review on prompt injection, uploaded file validation, and OCR workflows.
