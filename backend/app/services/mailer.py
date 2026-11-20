"""Envío del código de acceso (OTP). Backends: none | smtp | gmail."""
import base64
import logging
import smtplib
from email.mime.text import MIMEText

from ..core.config import settings

log = logging.getLogger(__name__)

SUBJECT = "PrácticaPE: tu código de acceso es {code}"


def render_body(code: str, minutes: int) -> str:
    return (
        "Tu código de acceso a PrácticaPE es: {code}\n\n"
        "Vence en {minutes} minutos. Si no lo pediste, ignora este correo.\n"
    ).format(code=code, minutes=minutes)


def _send_smtp(to: str, code: str) -> bool:
    if not settings.smtp_enabled:
        return False
    msg = MIMEText(render_body(code, settings.otp_expire_minutes), "plain", "utf-8")
    msg["Subject"] = SUBJECT.format(code=code)
    msg["From"] = settings.smtp_from
    msg["To"] = to
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
            if settings.smtp_tls:
                s.starttls()
            s.login(settings.smtp_user, settings.smtp_password)
            s.sendmail(settings.smtp_from, [to], msg.as_string())
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("smtp fallo: %s", e)
        return False


def _send_gmail(to: str, code: str) -> bool:
    """API de Gmail con el token OAuth ya autorizado (sin SMTP y sin coste)."""
    path = settings.gmail_token_path
    if not path or not __import__("os").path.isfile(path):
        return False
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except Exception:  # pragma: no cover - dependencia opcional
        return False

    scopes = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]
    try:
        creds = Credentials.from_authorized_user_file(path, scopes)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        raw = base64.urlsafe_b64encode(
            MIMEText(render_body(code, settings.otp_expire_minutes), "plain", "utf-8")
            .as_string()
            .encode("utf-8")
        ).decode("ascii")
        msg = {"raw": raw}
        service.users().messages().send(userId="me", body=msg).execute()
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("gmail fallo: %s", e)
        return False


def send_code(to: str, code: str) -> str:
    """Devuelve el canal usado: 'gmail' | 'smtp' | 'none'."""
    if settings.mail_backend == "gmail":
        return "gmail" if _send_gmail(to, code) else "none"
    if settings.mail_backend == "smtp":
        return "smtp" if _send_smtp(to, code) else "none"
    return "none"
