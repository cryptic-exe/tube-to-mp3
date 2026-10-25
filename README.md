# Tube to MP3

Convert YouTube videos and playlists to MP3.

- **Repo:** [github.com/cryptic-exe/tube-to-mp3](https://github.com/cryptic-exe/tube-to-mp3)
- **Web UI:** [tube-to-mp3-drab.vercel.app](https://tube-to-mp3-drab.vercel.app) (Vercel)
- **Download API** — FastAPI + `yt-dlp` + `ffmpeg` on Railway (see Deploy below)
- **CLI** — same conversion engine for local use

> For personal use with content you have rights to. Not affiliated with YouTube. A public downloader can be abused and may violate platform terms — the API key and rate limits are required for any public deploy.

## Architecture

| Piece | Where | Role |
|-------|--------|------|
| `apps/web` | Vercel | UI + BFF (keeps `DOWNLOAD_API_KEY` server-side) |
| `services/api` | Railway (Docker) | Probe, convert, stream MP3/ZIP |
| `packages/shared` | both | Shared `yt-dlp` helpers |
| `download_mp3.py` | local | CLI |

Vercel **cannot** run long downloads or system `ffmpeg`. The worker must live on Railway (or any Docker host).

## Quick start (local)

### 1. API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r services/api/requirements.txt

export DOWNLOAD_API_KEY=dev-secret
export PYTHONPATH="packages/shared:services/api"
uvicorn app.main:app --app-dir services/api --reload --port 8000
```

Requires [ffmpeg](https://ffmpeg.org/) on your PATH.

### 2. Web

```bash
cd apps/web
cp .env.example .env.local
# DOWNLOAD_API_URL=http://127.0.0.1:8000
# DOWNLOAD_API_KEY=dev-secret
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### CLI (optional)

```bash
source .venv/bin/activate
python download_mp3.py "https://www.youtube.com/watch?v=VIDEO_ID" -q 192
```

## Deploy

### GitHub

This repo is intended to be **public**. Push to GitHub, then connect Vercel and Railway to the same repository.

### Railway (API) — required for downloads to work

The Vercel UI is live, but conversions need this worker. Railway CLI login is interactive; use the dashboard:

1. Open [railway.app/new](https://railway.app/new) → **Deploy from GitHub** → `cryptic-exe/tube-to-mp3`.
2. Confirm build uses repo-root Dockerfile (`services/api/Dockerfile` / `railway.toml` is already in the repo).
3. Variables → add:

| Variable | Value |
|----------|--------|
| `DOWNLOAD_API_KEY` | same value as Vercel `DOWNLOAD_API_KEY` (see `apps/web/.env.local` locally) |
| `ALLOWED_ORIGINS` | `https://tube-to-mp3-drab.vercel.app` |
| `MAX_PLAYLIST_ENTRIES` | `50` |
| `RATE_LIMIT_PER_MINUTE` | `10` |

4. Settings → Networking → **Generate domain**. Copy the `https://….up.railway.app` URL.
5. Health check: `curl https://YOUR-RAILWAY-URL/health` → `{"status":"ok"}`.

### Vercel (web) — already deployed

Live at [tube-to-mp3-drab.vercel.app](https://tube-to-mp3-drab.vercel.app). Project root is `apps/web`.

After Railway is up, update Vercel env **Production + Preview**:

| Variable | Value |
|----------|--------|
| `DOWNLOAD_API_URL` | Railway public URL (no trailing slash) |
| `DOWNLOAD_API_KEY` | same secret as Railway |

Redeploy the web app (Deployments → Redeploy) so the BFF picks up the real API URL. The browser only talks to Next.js `/api/*`; the key never ships to the client.

## API (backend)

All `/v1/*` routes require `Authorization: Bearer <DOWNLOAD_API_KEY>`.

- `GET /health`
- `POST /v1/probe` — `{ "url" }`
- `POST /v1/jobs` — `{ "url", "quality": "128"|"192"|"256"|"320" }`
- `GET /v1/jobs/{id}`
- `GET /v1/jobs/{id}/file` — MP3 or ZIP

Jobs expire after about one hour (`JOB_TTL_SECONDS`).

## License / compliance

Use only for content you own or have permission to download. Operators are responsible for abuse controls and compliance with YouTube’s Terms of Service and applicable law.
