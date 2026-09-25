# Deploying the public demo (Netlify + Render + Aiven)

This deploys a **read-only public demo**: recruiters get a live link where they can
explore a real, pre-computed analysis (interactive map, per-building SAM/IoU
scores, the NLP chatbot, exports). The heavy live upload + SAM pipeline is
disabled (`DEMO_MODE=1`) so it runs on free/cheap tiers and can't be abused.

```
Browser ──▶ Netlify (Next.js frontend, CDN-proxies /api/* ) ──▶ Render (Django, demo mode) ──▶ Aiven (PostGIS, seeded)
```

Everything below is done by **you** — creating accounts and pasting env vars can't
be automated. The code and config are already prepared and committed.

---

## 0. One-time: push the deploy config to your GitHub repo

All the deploy files (`render.yaml`, `backend/Dockerfile.render`,
`backend/requirements-deploy.txt`, `netlify.toml`, the seed command, the
demo-mode backend changes) need to be on GitHub so Render and Netlify can build.

```bash
cd "<repo>"
git add -A
git commit -m "Add public demo deployment (Netlify + Render + Aiven, demo mode)"
git push myrepo main        # myrepo = your StillThere fork
```

---

## 1. Database — Aiven for PostgreSQL (free plan)

1. Sign up at https://aiven.io → **Create service → PostgreSQL → Free plan**.
2. Wait until it's *Running*, then open the service page and note the connection
   details (Overview tab): **Host, Port, Database name, User, Password**.
3. Enable PostGIS: open the **Query editor** (or connect with `psql`) and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```

## 2. Seed the Aiven database (run locally, one time)

Your local environment has GeoPandas; Render's slim image does not, so the seed
runs here and writes straight to Aiven.

```bash
cd "<repo>/backend"
export DJANGO_SETTINGS_MODULE=nkbp_backend.settings
export DB_HOST=<aiven-host> DB_PORT=<aiven-port> DB_NAME=<aiven-db>
export DB_USER=<aiven-user> DB_PASSWORD=<aiven-pass> DB_SSLMODE=require
export GDAL_LIBRARY_PATH="" GEOS_LIBRARY_PATH=""   # if your .env hard-codes macOS paths

python manage.py migrate
python manage.py seed_demo
```

Expected: `Seeded 1228 features and 1228 classified buildings ({'unchanged': 997,
'modified': 229, 'removed': 2}) ...`. (Use the venv that has GeoPandas installed.)

## 3. Backend — Render (free)

1. Get a **Gemini API key** (free): https://aistudio.google.com/apikey
2. Render → **New → Blueprint** → pick your repo. It reads `render.yaml` and
   creates the `stillthere-backend` web service (Docker, free plan).
3. Open the service → **Environment**, and fill the `sync:false` values:

   | Key | Value |
   |-----|-------|
   | `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | your Aiven values |
   | `DB_SSLMODE` | `require` (already set) |
   | `DEMO_MODE` | `1` (already set) |
   | `DJANGO_DEBUG` | `0` (already set) |
   | `DJANGO_SECRET_KEY` | auto-generated (already set) |
   | `DJANGO_ALLOWED_HOSTS` | `stillthere-backend.onrender.com` (your Render host; add the Netlify host too once you have it) |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://stillthere-backend.onrender.com` (add your Netlify URL later) |
   | `GEMINI_API_KEY` | your key from step 3.1 |

4. Deploy. When live, confirm: `https://<your-backend>.onrender.com/api/health/`
   returns `{"status":"ok"}` and `.../api/sessions/` lists the demo session.
   > Free tier sleeps after ~15 min idle; the first hit then takes ~50s to wake.

## 4. Frontend — Netlify (free)

1. Edit **`netlify.toml`** and replace the placeholder host in the `[[redirects]]`
   block with your real Render URL:
   ```toml
   to = "https://<your-backend>.onrender.com/api/:splat"
   ```
   Commit and push.
2. Netlify → **Add new site → Import from GitHub** → pick your repo.
   It reads `netlify.toml` (base `frontend`, build `npm run build`, Next.js
   plugin). Click **Deploy**.
3. When live, open your `https://<your-site>.netlify.app` link — the map,
   scores, chatbot, and exports should all work.

## 5. Close the loop (origins)

Back in **Render → Environment**, add your Netlify host to:
- `DJANGO_ALLOWED_HOSTS` → `stillthere-backend.onrender.com,<your-site>.netlify.app`
- `DJANGO_CSRF_TRUSTED_ORIGINS` → `https://stillthere-backend.onrender.com,https://<your-site>.netlify.app`
- `DJANGO_CORS_ALLOWED_ORIGINS` → `https://<your-site>.netlify.app`

Save (Render redeploys). Done — share the Netlify link.

---

## What works vs. what's disabled

| Feature | Demo |
|---|---|
| Interactive map, classification colours, per-building SAM/IoU scores | ✅ live |
| NLP chatbot (filter by material / height / size / zone) | ✅ live (needs `GEMINI_API_KEY`) |
| Export report | ✅ live |
| Upload a new shapefile / run live SAM | ⛔ returns "disabled in this public demo" |

## Notes & costs

- **Cost:** Aiven free + Render free + Netlify free = **$0**. Gemini has a free
  tier; heavy chatbot use could eventually incur Google charges — the demo is
  read-only so exposure is low.
- **Re-seeding:** `seed_demo` is idempotent — rerun it anytime to reset the data.
- **Login:** the demo is fully browsable without logging in. (Auth endpoints
  exist but the map/chatbot don't require them.)
- **Custom domain / no cold starts:** upgrade the Render service to a paid
  instance if you want the link always-warm for interviews.
