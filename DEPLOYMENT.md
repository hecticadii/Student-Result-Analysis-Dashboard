# Deployment Guide

## Recommended Path

This app is easiest to deploy on any platform that can run a Docker container and attach persistent storage.

Why this matters:

- The app now uses SQLAlchemy and can point at either SQLite or PostgreSQL.
- If you use local SQLite, the Docker image writes that data to `/data` by default.
- If you use PostgreSQL via `DATABASE_URL`, user accounts and history survive restarts and redeploys without relying on the filesystem.
- Mount a persistent volume at `/data` only if you want to keep SQLite files or a file-based allowlist.

## Render Blueprint Setup

If you cannot find the Postgres service in the Render dashboard, use the `render.yaml` file in this repo instead of creating things by hand.

1. Push this repo to GitHub with `render.yaml` included.
2. In Render, open `Blueprints`.
3. Click `New Blueprint Instance`.
4. Select this repository.
5. Render will create or attach:
   - the web service `Student-Result-Analysis-Dashboard`
   - the PostgreSQL database `airas-postgres`
   - the `DATABASE_URL` env var wired to that database automatically
6. If Render prompts for `AIRAS_ALLOWED_EMAILS`, paste your faculty allowlist there.

Important:

- The permanent login storage is the PostgreSQL database.
- The blueprint creates a paid `basic-1gb` Postgres database, which avoids the 30-day expiry of Render free databases.
- Render free web services cannot keep SQLite files across redeploys.
- For truly durable auth on Render, keep the PostgreSQL database created by the blueprint.

## Required Configuration

At minimum, set one of these so faculty can log in:

- `AIRAS_ALLOWED_EMAILS=faculty1@college.edu,faculty2@college.edu`
- Or place `faculty_allowlist.txt` inside the persistent data directory

For durable production storage on Render, also set:

- `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME`

Optional settings:

- `AIRAS_REGISTRATION_SECRET` to require an invite key during account creation
- `AIRAS_SMTP_HOST`, `AIRAS_SMTP_PORT`, `AIRAS_SMTP_USER`, `AIRAS_SMTP_PASSWORD`, `AIRAS_SMTP_FROM`, `AIRAS_SMTP_USE_TLS` for email verification
- `AIRAS_EMAIL_DEBUG=1` to print verification codes to logs instead of sending email
- `AIRAS_BYPASS_FACULTY_ALLOWLIST=1` for local testing only
- `AIRAS_DATA_DIR=/data` if you keep SQLite and the allowlist on a mounted disk

See [`env.example`](env.example) for the full set.

## Docker Build

```bash
docker build -t airas .
```

## Docker Run

```bash
docker run --name airas \
  -p 8501:8501 \
  -e AIRAS_ALLOWED_EMAILS=faculty@college.edu \
  -v airas-data:/data \
  airas
```

Then open `http://localhost:8501`.

For PostgreSQL-backed production, pass `DATABASE_URL` instead of relying on the local SQLite file.

## Move Existing Accounts To Render

If you already created accounts in your local `data/app.db`, those users will not appear on Render until you copy them into the Render PostgreSQL database.

Run this from your project folder after setting `DATABASE_URL` to your Render PostgreSQL connection string:

```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME"
python migrate_users_to_postgres.py --source data/app.db --include-history
```

What this does:

- Copies every local user into the PostgreSQL database
- Preserves hashed passwords
- Keeps duplicate emails from being created twice
- Optionally copies history rows too

After migration, redeploy the Render service and test login again.

## Cloud Host Checklist

Use a host that supports:

- A Dockerfile-based web service
- A persistent disk or mounted volume if you keep SQLite/allowlist files
- Environment variables or secrets
- PostgreSQL support or a managed Postgres add-on

Deploy with this checklist:

1. Build from this repository using the included `Dockerfile`.
2. Expose port `8501`, or let the host provide a `PORT` environment variable.
3. For best durability on Render, create a managed PostgreSQL database and set `DATABASE_URL`.
4. Set `AIRAS_ALLOWED_EMAILS` or provide `/data/faculty_allowlist.txt`.
5. Add SMTP secrets only if you want email verification.
6. Mount persistent storage at `/data` only if you are keeping SQLite or a file-based allowlist.

## Streamlit Community Cloud Note

This repo can run on Streamlit Community Cloud because `streamlit_app.py`, `dashboard.py`, `requirements.txt`, and `.streamlit/config.toml` are already present.

When creating the app, set the main file path to `streamlit_app.py`.

However, Streamlit Community Cloud still uses ephemeral filesystem storage. If you deploy there, avoid relying on local SQLite files for persistence and use a hosted database instead.
