import unittest
from unittest.mock import patch

from utils import email_otp


class TestEmailOtp(unittest.TestCase):
    def test_example_smtp_credentials_are_rejected_before_connection(self):
        with patch.object(email_otp.config, "SMTP_USERNAME", "yourgmail@gmail.com"), \
                patch.object(email_otp.config, "SMTP_PASSWORD", "your-16-character-google-app-password"), \
                patch.object(email_otp.config, "SMTP_FROM_EMAIL", "yourgmail@gmail.com"), \
                patch.object(email_otp.smtplib, "SMTP_SSL") as smtp:
            with self.assertRaisesRegex(
                email_otp.EmailConfigurationError,
                "Google App Password",
            ):
                email_otp.send_login_otp("Lecturer", "lecturer@example.com", "123456")

        smtp.assert_not_called()

    def test_gmail_app_password_grouping_spaces_are_removed(self):
        with patch.object(email_otp.config, "SMTP_HOST", "smtp.gmail.com"), \
                patch.object(email_otp.config, "SMTP_PORT", 465), \
                patch.object(email_otp.config, "SMTP_USERNAME", "lecturer@example.com"), \
                patch.object(email_otp.config, "SMTP_PASSWORD", "abcd efgh ijkl mnop"), \
                patch.object(email_otp.config, "SMTP_FROM_EMAIL", "lecturer@example.com"), \
                patch.object(email_otp.smtplib, "SMTP_SSL") as smtp:
            email_otp.send_login_otp("Lecturer", "lecturer@example.com", "123456")

        server = smtp.return_value.__enter__.return_value
        server.login.assert_called_once_with("lecturer@example.com", "abcdefghijklmnop")
        server.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
