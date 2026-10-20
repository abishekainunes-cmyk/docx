# NUNES Catalogue Studio - Vercel

Deploy the contents of this directory as the Vercel project root (Python / Other framework). The website runs via `api/index.py` and uses the existing `generator.py` plus `templates/` assets.

## Production environment variables (Vercel > Project > Settings > Environment Variables)

- `NUNES_ADMIN_PASSWORD`: strong random password required for all `/api/*` product and generation actions.
- `GOOGLE_SERVICE_ACCOUNT_JSON`: full service-account JSON **as a secret environment variable**, not a committed file. Share the `total price list` sheet with the service-account email, and enable Google Sheets API.

The base `/api/health` URL reports non-secret configuration status; `GET /api/products?q=...` searches the private sheet; `POST /api/generate` makes individual PDFs from existing Nunes templates.

**Important architecture:** Vercel functions are short-lived and `/tmp` data is ephemeral. This release is **on-demand generation only**, not unattended generation of all ~127K source rows. For 100K+ product automation, run the original `generator.py` as a persistent worker (e.g. Render background worker or Windows service), with Neon database checkpoints and durable object storage (Vercel Blob or S3). This is not implemented by the Vercel web interface alone.

No generated PDF or Google account credentials are committed. Mini catalogues use up to ten other products from the current search result. For category-aware related-product selection across the entire sheet, a persistent indexed database worker is still required.

For local test: `pip install -r requirements.txt`, set NUNES_ADMIN_PASSWORD, then `python webapp.py`, open http://127.0.0.1:8788.
