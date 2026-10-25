import asyncio
import smtplib
from email.message import EmailMessage


class EmailSmtp:
    def __init__(self, host: str, port: int, user: str, password: str, to: str):
        self.host, self.port, self.user, self.password, self.to = host, port, user, password, to

    def _send(self, subject: str, body: str, attachment: tuple[str, bytes] | None) -> None:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = subject, self.user, self.to
        msg.set_content(body)
        if attachment:
            name, content = attachment
            msg.add_attachment(
                content,
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=name,
            )
        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self.user, self.password)
            smtp.send_message(msg)

    async def send(self, subject: str, body: str, attachment=None) -> None:
        await asyncio.to_thread(self._send, subject, body, attachment)
