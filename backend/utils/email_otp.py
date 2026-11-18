"""Email delivery for login verification codes."""
import smtplib
from email.message import EmailMessage

from config import config


class EmailConfigurationError(RuntimeError):
    """Raised when the local SMTP settings are missing or still use examples."""


def _is_example_value(value: str) -> bool:
    lowered = value.strip().lower()
    return any(marker in lowered for marker in ("yourgmail", "your-16-character", "replace-with"))


def send_login_otp(name: str, recipient: str, otp: str) -> None:
    settings = (config.SMTP_USERNAME, config.SMTP_PASSWORD, config.SMTP_FROM_EMAIL)
    if any(not value or _is_example_value(value) for value in settings):
        raise EmailConfigurationError(
            "SMTP is not configured: replace the example SMTP_USERNAME, SMTP_PASSWORD, "
            "and SMTP_FROM_EMAIL values in backend/.env. For Gmail, use a Google App Password."
        )

    message = EmailMessage()
    message["Subject"] = "SecureExam AI - Login verification code"
    message["From"] = config.SMTP_FROM_EMAIL
    message["To"] = recipient
    message.set_content(
        f"Hello {name},\\n\\n"
        f"Your SecureExam AI login verification code is: {otp}\\n\\n"
        f"This code expires in {config.EMAIL_OTP_TTL_MINUTES} minutes. "
        "Do not share this code with anyone.\\n\\n"
        "If you did not try to sign in, you can ignore this email."
    )
    with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as server:
        password = config.SMTP_PASSWORD.strip()
        if config.SMTP_HOST.lower() in ("smtp.gmail.com", "smtp.googlemail.com"):
            password = password.replace(" ", "")
        server.login(config.SMTP_USERNAME, password)
        server.send_message(message)
