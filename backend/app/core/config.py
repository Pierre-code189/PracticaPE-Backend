import os
import secrets

from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.getenv("PRACTICAPE_DATA_DIR", os.path.join(BASE_DIR, "data"))


def _load_secret(env_name: str, path: str, nbytes: int = 48) -> str:
    """Devuelve el secreto del entorno o de un fichero 600; si no existe, lo genera."""
    val = os.getenv(env_name)
    if val:
        return val
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            val = fh.read().strip()
        if val:
            return val
    val = secrets.token_urlsafe(nbytes)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(val)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return val


class Settings(BaseSettings):
    app_name: str = "PracticaPE"
    database_url: str = os.getenv(
        "PRACTICAPE_DB", "sqlite:///" + os.path.join(DATA_DIR, "practicape.db")
    )
    # Sin valor por defecto embebido: si no hay SECRET_KEY se genera uno en data/.secret (600).
    secret_key: str = _load_secret("SECRET_KEY", os.path.join(DATA_DIR, ".secret"))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    otp_request_window_minutes: int = 10
    otp_max_per_window: int = 3
    otp_dev_code: bool = os.getenv("OTP_DEV_CODE", "0") == "1"

    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587") or 587)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "no-reply@practicape.pe")
    smtp_tls: bool = os.getenv("SMTP_TLS", "1") == "1"
    # none | smtp | gmail  (gmail usa la API de Gmail, sin SMTP y sin coste)
    mail_backend: str = os.getenv("MAIL_BACKEND", "none").strip().lower()
    gmail_token_path: str = os.getenv("GMAIL_TOKEN_PATH", "")
    gmail_from: str = os.getenv("GMAIL_FROM", "")

    cors_origins: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8002,http://127.0.0.1:8002,https://practicape.apioai.online",
    )
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8002")
    upload_max_mb: int = 5
    allowed_upload_types: str = "image/jpeg,image/png,image/webp"

    piura_districts: list = [
        "Piura", "Castilla", "Veintisseis de Octubre", "Cura Mori", "El Tallan",
        "Chulucanas", "Morropon", "Huarmaca", "La Arena", "La Union", "Catacaos",
        "C Tambogrande", "Tambogrande", "Las Lomas", "Sullana", "Bellavista",
        "Marcavelica", "Querecotillo", "Ignacio Escudero", "Miguel Checa",
        "Salitral", "Paita", "Talara", "Manccora", "Mancora", "Los Organos",
        "Pariñas", "El Alto", "La Brea", "Lobitos",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_list(self) -> list:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def upload_allow(self) -> set:
        return {x.strip() for x in self.allowed_upload_types.split(",") if x.strip()}

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)


settings = Settings()
