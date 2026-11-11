import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "PracticaPE"
    database_url: str = os.getenv("PRACTICAPE_DB", "sqlite:///./data/practicape.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-crouton-alpha-change-in-prod")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    otp_expire_minutes: int = 10
    otp_dev_code: bool = os.getenv("OTP_DEV_CODE", "1") == "1"
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


settings = Settings()
