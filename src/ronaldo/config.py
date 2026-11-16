"""Settings loaded from the .env file."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    sender_email: str = os.getenv("SENDER_EMAIL", "")
    sender_password: str = os.getenv("SENDER_APP_PASSWORD", "")
    sender_name: str = os.getenv("SENDER_NAME", "")
    sender_phone: str = os.getenv("SENDER_PHONE", "")
    sender_linkedin: str = os.getenv("SENDER_LINKEDIN", "")
    experience: str = os.getenv("EXPERIENCE", "1 year and 4 months")
    resume_path: Path = Path(os.getenv("RESUME_PATH", "resume.pdf"))
    # Pause between emails so Gmail doesn't flag the account as spam.
    delay_seconds: float = float(os.getenv("DELAY_SECONDS", "20"))
    # Hard cap per run; Gmail allows roughly 500/day for personal accounts.
    max_per_run: int = int(os.getenv("MAX_PER_RUN", "50"))
    sent_log: Path = Path(os.getenv("SENT_LOG", "sent_log.csv"))

    def check(self) -> None:
        missing = [
            name
            for name, value in [
                ("SENDER_EMAIL", self.sender_email),
                ("SENDER_APP_PASSWORD", self.sender_password),
                ("SENDER_NAME", self.sender_name),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing in .env: {', '.join(missing)}")


settings = Settings()
