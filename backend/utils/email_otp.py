"""Email delivery for login verification codes."""
import smtplib
from email.message import EmailMessage

from config import config


def send_login_otp(name: str, recipient: str, otp: str) -> None:
    if not config.SMTP_USERNAME or not config.SMTP_PASSWORD or not config.SMTP_FROM_EMAIL:
        raise RuntimeError("SMTP credentials are not configured")
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
        server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.send_message(message)
