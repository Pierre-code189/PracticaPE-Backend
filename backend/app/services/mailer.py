"""Envío del código de acceso.

Dos canales, sin coste:
  * API de Gmail (MAIL_BACKEND=gmail): usa un token OAuth ya autorizado con el
    permiso gmail.send. No requiere SMTP ni contraseñas de aplicación.
  * SMTP (MAIL_BACKEND=smtp): solo si están definidas SMTP_HOST/SMTP_USER/SMTP_PASSWORD.

Si no hay canal configurado, no envía (la web lo indica con channel="none").
"""
import base64
import json
import os
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText

from ..core.config import settings

GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"


def _texto(name: str, code: str) -> str:
    return (
        f"Hola {name or 'usuario'},\n\n"
        f"Tu código de acceso a {settings.app_name} es: {code}\n"
        f"Vence en {settings.otp_expire_minutes} minutos. Si no lo pediste, ignora este correo.\n\n"
        f"{settings.app_name} · Piura, Perú"
    )


def _subject(code: str) -> str:
    return f"{settings.app_name}: tu código de acceso es {code}"


def send_otp(email: str, code: str, name: str = "") -> bool:
    if settings.mail_backend == "gmail":
        return _send_gmail(email, code, name)
    if settings.mail_backend == "smtp" or settings.smtp_enabled:
        return _send_smtp(email, code, name)
    return False


def _send_smtp(email: str, code: str, name: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = _subject(code)
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg.set_content(_texto(name, code))
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            if settings.smtp_tls:
                s.starttls()
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
        return True
    except Exception:
        return False


def _send_gmail(email: str, code: str, name: str) -> bool:
    path = settings.gmail_token_path
    if not path or not os.path.exists(path):
        return False
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except Exception:
        return False
    try:
        creds = Credentials.from_authorized_user_file(path, [GMAIL_SEND])
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Guarda el access token renovado (conserva el refresh token).
            with open(path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            os.chmod(path, 0o600)
        sender = settings.gmail_from
        service = build("gmail", "v1", credentials=creds)
        if not sender:
            sender = service.users().getProfile(userId="me").execute().get("emailAddress")
        msg = MIMEText(_texto(name, code))
        msg["Subject"] = _subject(code)
        msg["From"] = sender
        msg["To"] = email
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception:
        return False
