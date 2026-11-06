from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings
import os

url = settings.database_url
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
if url.startswith("sqlite"):
    path = url.replace("sqlite:///", "")
    if path and path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
engine = create_engine(url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from .. import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
