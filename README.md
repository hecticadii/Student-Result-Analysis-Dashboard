# Academic Result Intelligence Dashboard

This project analyzes university result workbooks and turns them into a Streamlit dashboard with term-wise analytics, student drill-down views, subject performance summaries, and exportable Excel reports.

The repo includes:

- A Streamlit web app for faculty login, workbook upload, interactive analysis, and downloads
- A result-processing engine that auto-detects common Excel result-sheet layouts
- An Excel report generator for summary sheets, subject analysis, grade sheets, toppers, and student matrix exports
- Sample input/output files so the project can be tried immediately

## Features

- Faculty login and account creation backed by SQLite
- Upload and analyze `.xlsx` semester result files
- Auto-detect workbook sheet structure, subject blocks, SGPA, grade, and term labels
- Multi-term support for sheets containing `Term`, `Sem`, or `Semester` sections
- Dashboard tabs for:
  - Overview
  - Subject Intelligence
  - Grade Sheet
  - Student Explorer
  - History
  - Reporting
- Export options for CSV, TXT, ZIP bundle, and formatted Excel report
- Session persistence for uploaded files and user activity history
- Automatic exclusion of blank or invalid student rows from analysis

## Tech Stack

- Python 3.13.5
- Streamlit 1.54.0
- pandas 2.3.3
- openpyxl 3.1.5
- SQLite

## Project Structure

```text
airas/
|-- dashboard.py              # Main Streamlit dashboard
|-- result_engine.py          # Workbook parsing and analytics engine
|-- report_generator.py       # Formatted Excel report generation
|-- app.py                    # Simple script entry point for sample report generation
|-- data/
|   |-- DS Result.xlsx        # Sample workbook
|   `-- app.db                # SQLite database for users, sessions, and history
|-- assets/
|   `-- login image.jpg       # Login screen background
|-- Final_Result_Report*.xlsx # Sample generated reports
`-- venv/                     # Local virtual environment
```

## Getting Started

### 1. Create or activate a virtual environment

Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

`requirements.txt` is currently empty, so install the runtime packages directly:

```powershell
python -m pip install streamlit pandas openpyxl
```

### 3. Run the dashboard

```powershell
python -m streamlit run dashboard.py
```

Streamlit will start a local server, typically at:

```text
http://127.0.0.1:8501
```

### 4. Use the app

1. Create an account from the login screen or sign in with an existing one.
2. Upload an Excel workbook in `.xlsx` format.
3. Select the target sheet from the sidebar.
4. Review the auto-detected academic profile and adjust it if needed.
5. Explore analytics and download reports.

## Script-Based Usage

If you only want to generate a report from the sample workbook without opening the dashboard:

```powershell
python app.py
```

This uses `data/DS Result.xlsx` and generates `Final_Result_Report.xlsx`.

## Input Workbook Expectations

The engine is designed for result sheets similar to the included sample workbook. It works best when the sheet contains:

- A student identifier column such as `Roll No` or `PRN`
- A student name column
- An `SGPA` or `GPA` column
- Subject blocks with result or marks fields such as `Int`, `Ext`, `Tot`, and `P/F`
- Optional term labels like `Term V`, `Sem 5`, or `Semester 5`

It can tolerate:

- Metadata rows above the actual header
- Multi-row headers
- Subject names that include course codes in parentheses
- Workbooks containing multiple sheets

During loading, the engine removes clearly blank or invalid student rows from analytics and keeps them available as excluded records in the dashboard.

## Outputs

The dashboard can generate:

- Insights CSV
- Insights text report
- Subject analysis CSV
- Full analysis ZIP bundle
- Formatted Excel report such as `Final_Result_Report_Term_V.xlsx`

The Excel report includes sheets such as:

- `Summary`
- `Subject Analysis`
- `Interpretation`
- `Grade Sheet`
- `Class Toppers`
- `Student Matrix`

## Database Notes

The app stores data in `data/app.db`, including:

- User accounts
- Login sessions
- Upload history
- Uploaded workbook bytes for session restore

If you want a clean start, back up or remove the database file before launching the app again.

## Main Modules

### `dashboard.py`

Runs the Streamlit UI, login flow, upload flow, term tabs, history tracking, theme handling, and export actions.

### `result_engine.py`

Loads Excel sheets with pandas, detects headers and terms, identifies key columns, computes class overview metrics, builds subject analysis, grade summaries, toppers, and student-level reports.

### `report_generator.py`

Builds a formatted Excel workbook using `openpyxl` styles and multiple report sheets for academic review.

### `app.py`

Shows a minimal example of calling `ResultEngine` and `ReportGenerator` directly from Python.

## Sample Data

The repository already includes a sample workbook:

- `data/DS Result.xlsx`

In the current sample, the workbook contains a `test` sheet and represents a semester result layout with term metadata and subject-wise marks.

## Notes

- This project is set up for local use and faculty workflow automation, not hardened production deployment.
- The committed SQLite database may already contain local history or user data depending on prior use.
- `dashboard.html` and the `Aryan-ui-droid` folder appear to be unused prototype or leftover UI files and are not required to run the Python app.
