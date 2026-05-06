# Academic Result Intelligence Dashboard

AIRAS is a Streamlit-based dashboard for faculty to upload semester result workbooks, analyze performance, inspect subject trends, and export polished academic reports.

## What It Does

- Secure faculty login with SQLite-backed users and session restore
- Upload and analyze `.xlsx` result sheets
- Auto-detect subjects, grades, SGPA, and term-wise sections
- Explore class overview, subject intelligence, grade sheets, student drill-down, and history
- Export CSV, TXT, ZIP, and formatted Excel reports

## Local Run

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run dashboard.py
```

The app normally starts at `http://127.0.0.1:8501`.

## Deployment

This repo is set up for container deployment.

- [`Dockerfile`](Dockerfile) starts the app in a deployable container
- [`start.py`](start.py) respects cloud-provided `PORT`
- SQLite data defaults to `/data` inside the container so you can mount persistent storage
- [`streamlit_app.py`](streamlit_app.py) is the Streamlit Community Cloud entrypoint

Full instructions are in [`DEPLOYMENT.md`](DEPLOYMENT.md).

## Required Configuration

Before deploying, configure at least one faculty access source:

- `AIRAS_ALLOWED_EMAILS=faculty1@college.edu,faculty2@college.edu`
- Or a persistent `faculty_allowlist.txt` in the app data directory

Optional configuration includes SMTP settings for email verification and `AIRAS_REGISTRATION_SECRET` for invite-only registration. See [`env.example`](env.example).

## Main Files

- [`dashboard.py`](dashboard.py): Streamlit UI and auth flow
- [`streamlit_app.py`](streamlit_app.py): thin wrapper for Streamlit Community Cloud
- [`result_engine.py`](result_engine.py): workbook parsing and analytics
- [`report_generator.py`](report_generator.py): formatted Excel report generation
- [`app.py`](app.py): script example for offline report creation

## Notes

- The app can run on Streamlit Community Cloud, but SQLite data there is ephemeral.
- For durable user accounts and upload history, use a Docker-capable host with persistent storage.
