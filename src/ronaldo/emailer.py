"""Read HR contacts from a CSV and email each one your resume."""

import csv
import io
import re
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from .config import Settings, settings

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")

# Column names we recognise (case-insensitive). Only the email column is required.
EMAIL_COLS = ("email", "email id", "email_id", "hr email", "hr_email", "mail", "e-mail")
NAME_COLS = ("name", "hr name", "hr_name", "first name", "first_name", "contact")
COMPANY_COLS = ("company", "company name", "company_name", "organization", "organisation")


@dataclass
class Contact:
    email: str
    name: str = ""
    company: str = ""


@dataclass
class Result:
    email: str
    status: str  # sent | skipped | failed | dry-run
    detail: str = ""


def _pick(row: dict, candidates: tuple[str, ...]) -> str:
    lowered = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
    for col in candidates:
        if lowered.get(col):
            return lowered[col]
    return ""


def parse_contacts(csv_text: str) -> tuple[list[Contact], list[Result]]:
    """Return valid unique contacts plus rows that were rejected."""
    reader = csv.DictReader(io.StringIO(csv_text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    if not any(h in EMAIL_COLS for h in headers):
        raise ValueError(
            f"No email column found. Headers were {reader.fieldnames}. "
            f"Name one of: {', '.join(EMAIL_COLS)}"
        )

    contacts, rejected, seen = [], [], set()
    for row in reader:
        email = _pick(row, EMAIL_COLS).lower()
        if not email:
            continue
        if not EMAIL_RE.match(email):
            rejected.append(Result(email, "skipped", "invalid email address"))
            continue
        if email in seen:
            continue
        seen.add(email)
        contacts.append(Contact(email, _pick(row, NAME_COLS), _pick(row, COMPANY_COLS)))
    return contacts, rejected


def build_subject(cfg: Settings = settings) -> str:
    return f"Application for Data Analyst / Data Scientist / AI Engineer Roles - {cfg.sender_name}"


def build_body(contact: Contact, cfg: Settings = settings) -> str:
    greeting = f"Dear {contact.name.split()[0]}," if contact.name else "Dear Hiring Manager,"
    at_company = f" at {contact.company}" if contact.company else " in your organization"
    signature = "\n".join(
        line for line in [cfg.sender_name, cfg.sender_phone, cfg.sender_email, cfg.sender_linkedin] if line
    )
    return f"""{greeting}

I hope you are doing well. I am writing to express my interest in Data Analyst, Data Scientist, or AI Engineer opportunities{at_company}.

I hold a Master's degree in Data Science and have {cfg.experience} of professional experience as a Data QA Engineer. In this role I have worked on validating data pipelines, ensuring data quality and accuracy, writing SQL to test and reconcile large datasets, and automating quality checks. This work has given me a strong foundation in data handling and attention to detail, and I am now keen to apply my analytics, machine learning, and AI skills in a dedicated data or AI role.

I would be grateful for the opportunity to contribute to your team. Please find my resume attached for your review. I would welcome the chance to discuss how my background could add value, and I am happy to share any further information you may need.

Thank you for your time and consideration.

Best regards,
{signature}
"""


def build_message(contact: Contact, resume: bytes, resume_name: str, cfg: Settings = settings) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((cfg.sender_name, cfg.sender_email))
    msg["To"] = contact.email
    msg["Subject"] = build_subject(cfg)
    msg.set_content(build_body(contact, cfg))
    msg.add_attachment(resume, maintype="application", subtype="pdf", filename=resume_name)
    return msg


def already_sent(cfg: Settings = settings) -> set[str]:
    if not cfg.sent_log.exists():
        return set()
    with cfg.sent_log.open(newline="", encoding="utf-8") as f:
        return {r["email"] for r in csv.DictReader(f) if r.get("status") == "sent"}


def _log(result: Result, cfg: Settings) -> None:
    new = not cfg.sent_log.exists()
    with cfg.sent_log.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "email", "status", "detail"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), result.email, result.status, result.detail])


def send_all(
    csv_text: str,
    resume: bytes | None = None,
    resume_name: str | None = None,
    dry_run: bool = True,
    cfg: Settings = settings,
) -> list[Result]:
    """Email every contact in the CSV. Defaults to dry run, so nothing is sent unless asked."""
    if resume is None:
        if not cfg.resume_path.exists():
            raise FileNotFoundError(f"Resume not found at {cfg.resume_path}. Set RESUME_PATH in .env.")
        resume = cfg.resume_path.read_bytes()
        resume_name = cfg.resume_path.name
    resume_name = resume_name or "resume.pdf"

    contacts, results = parse_contacts(csv_text)
    done = already_sent(cfg)

    todo = []
    for c in contacts:
        if c.email in done:
            results.append(Result(c.email, "skipped", "already emailed in an earlier run"))
        else:
            todo.append(c)
    for c in todo[cfg.max_per_run :]:
        results.append(Result(c.email, "skipped", f"over MAX_PER_RUN={cfg.max_per_run}; run again later"))
    todo = todo[: cfg.max_per_run]

    if dry_run:
        results.extend(Result(c.email, "dry-run", "would send") for c in todo)
        return results

    cfg.check()
    with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ssl.create_default_context()) as smtp:
        try:
            smtp.login(cfg.sender_email, cfg.sender_password.replace(" ", ""))
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as e:
            raise RuntimeError(
                "Gmail rejected the login. SENDER_APP_PASSWORD must be a 16-letter App Password "
                "from https://myaccount.google.com/apppasswords, not your normal Gmail password. "
                f"(Gmail said: {e})"
            ) from e
        for i, c in enumerate(todo):
            try:
                smtp.send_message(build_message(c, resume, resume_name, cfg))
                r = Result(c.email, "sent")
            except smtplib.SMTPException as e:
                r = Result(c.email, "failed", str(e))
            results.append(r)
            _log(r, cfg)
            print(f"[{i + 1}/{len(todo)}] {r.status}: {c.email} {r.detail}")
            if i < len(todo) - 1:
                time.sleep(cfg.delay_seconds)
    return results


def preview(csv_text: str, cfg: Settings = settings) -> str:
    contacts, _ = parse_contacts(csv_text)
    if not contacts:
        return "No valid contacts found."
    c = contacts[0]
    return f"To: {c.email}\nSubject: {build_subject(cfg)}\n\n{build_body(c, cfg)}"


def read_csv_file(path: str | Path) -> str:
    # utf-8-sig strips the BOM Excel adds when saving CSVs.
    return Path(path).read_text(encoding="utf-8-sig")
