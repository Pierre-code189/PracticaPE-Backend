"""Envío de correo con smtplib (stdlib). Si SMTP no está configurado, no envía."""
import smtplib
from email.message import EmailMessage

from ..core.config import settings


def send_otp(email: str, code: str, name: str = "") -> bool:
    if not settings.smtp_enabled:
        return False
    msg = EmailMessage()
    msg["Subject"] = f"{settings.app_name}: tu código de acceso es {code}"
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg.set_content(
        f"Hola {name or 'usuario'},\n\n"
        f"Tu código de acceso a {settings.app_name} es: {code}\n"
        f"Vence en {settings.otp_expire_minutes} minutos. Si no lo pediste, ignora este correo.\n\n"
        f"{settings.app_name} · Piura, Perú"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            if settings.smtp_tls:
                s.starttls()
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
        return True
    except Exception:
        return False
