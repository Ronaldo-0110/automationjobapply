"""Command line:  uv run ronaldo hr_contacts.csv [--resume my_resume.pdf] [--send]"""

import argparse
from pathlib import Path


def main() -> None:
    from .emailer import preview, read_csv_file, send_all

    p = argparse.ArgumentParser(description="Email your resume to every HR contact in a CSV.")
    p.add_argument("csv", help="CSV file with an 'email' column (optional: name, company)")
    p.add_argument("--resume", help="Resume PDF (default: RESUME_PATH from .env)")
    p.add_argument("--send", action="store_true", help="Actually send. Without this it's a dry run.")
    args = p.parse_args()

    csv_text = read_csv_file(args.csv)
    resume = Path(args.resume) if args.resume else None

    print("---- Email preview (first contact) ----")
    print(preview(csv_text))
    print("---------------------------------------")

    if args.send and input("Send real emails now? Type 'yes': ").strip().lower() != "yes":
        print("Cancelled.")
        return

    results = send_all(
        csv_text,
        resume.read_bytes() if resume else None,
        resume.name if resume else None,
        dry_run=not args.send,
    )
    for r in results:
        print(f"{r.status:8} {r.email} {r.detail}")
    if not args.send:
        print("\nDry run only. Add --send to actually email.")
