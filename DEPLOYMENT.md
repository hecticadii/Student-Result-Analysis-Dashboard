# Deployment Guide

## Recommended Path

This app is easiest to deploy on any platform that can run a Docker container and attach persistent storage.

Why this matters:

- The app stores users, sessions, upload history, and cached uploads in SQLite.
- The Docker image writes that data to `/data` by default.
- Mount a persistent volume at `/data` so accounts and history survive restarts.

## Required Configuration

At minimum, set one of these so faculty can log in:

- `AIRAS_ALLOWED_EMAILS=faculty1@college.edu,faculty2@college.edu`
- Or place `faculty_allowlist.txt` inside the persistent data directory

Optional settings:

- `AIRAS_REGISTRATION_SECRET` to require an invite key during account creation
- `AIRAS_SMTP_HOST`, `AIRAS_SMTP_PORT`, `AIRAS_SMTP_USER`, `AIRAS_SMTP_PASSWORD`, `AIRAS_SMTP_FROM`, `AIRAS_SMTP_USE_TLS` for email verification
- `AIRAS_EMAIL_DEBUG=1` to print verification codes to logs instead of sending email
- `AIRAS_BYPASS_FACULTY_ALLOWLIST=1` for local testing only

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

## Cloud Host Checklist

Use a host that supports:

- A Dockerfile-based web service
- A persistent disk or mounted volume
- Environment variables or secrets

Deploy with this checklist:

1. Build from this repository using the included `Dockerfile`.
2. Expose port `8501`, or let the host provide a `PORT` environment variable.
3. Mount persistent storage at `/data`.
4. Set `AIRAS_ALLOWED_EMAILS` or provide `/data/faculty_allowlist.txt`.
5. Add SMTP secrets only if you want email verification.

## Streamlit Community Cloud Note

This repo can run on Streamlit Community Cloud because `streamlit_app.py`, `dashboard.py`, `requirements.txt`, and `.streamlit/config.toml` are already present.

When creating the app, set the main file path to `streamlit_app.py`.

However, Streamlit Community Cloud uses ephemeral filesystem storage, so SQLite-backed users, sessions, and history may reset when the app restarts. For durable logins and history, prefer a Docker host with persistent storage.
