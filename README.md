# Job Application Mailer

Upload a CSV of HR contacts and this app emails each one a cover letter with your resume attached, through your Gmail account.

Built with Python, FastAPI and Gmail SMTP. It has a web page for uploading files and a command-line version.

## Features

- **Personalised greeting.** Uses each contact's name and company when the CSV includes them; otherwise "Dear Hiring Manager".
- **Dry run by default.** Preview exactly who will be emailed before anything is sent.
- **No duplicates.** Every send is logged to `sent_log.csv`, so a contact is never emailed twice across runs.
- **Spam-safe pacing.** Waits between emails (default 20 s) and caps each run (default 50).
- **Input checks.** Skips invalid and duplicate addresses and handles CSVs saved from Excel.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <this repo>
cd <repo folder>
uv sync
cp .env.example .env    # then fill in .env
```

In `.env`, set `SENDER_APP_PASSWORD` to a Gmail **App Password**, not your normal password. Create one at https://myaccount.google.com/apppasswords; 2-Step Verification must be on. Set `RESUME_PATH` to your resume PDF.

## Usage

### Web app

```bash
uv run uvicorn ronaldo.api:app --reload
```

Open http://127.0.0.1:8000, choose your CSV (and optionally a resume) and click **Preview email**. Tick **Actually send** and click **Run** to send. API docs are at http://127.0.0.1:8000/docs.

### Command line

```bash
uv run ronaldo contacts.csv           # dry run: shows the email and who would get it
uv run ronaldo contacts.csv --send    # sends, after you confirm
```

## CSV format

An `email` column is required. `name` and `company` are optional. See [sample_hr_contacts.csv](sample_hr_contacts.csv).

```csv
name,email,company
Priya Sharma,priya.hr@example.com,Acme Analytics
```

## Customising the email

Edit `build_subject` and `build_body` in [src/ronaldo/emailer.py](src/ronaldo/emailer.py).

## Project layout

```
src/ronaldo/
  api.py      FastAPI app and upload page
  emailer.py  CSV parsing, email building, sending, logging
  config.py   settings loaded from .env
  __init__.py command-line entry point
```

## Responsible use

Email only addresses that are publicly listed for recruiting, keep the volume low, and stop contacting anyone who asks you to.
