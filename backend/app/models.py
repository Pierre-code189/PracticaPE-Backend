from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .core.database import Base


def now():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    # `email` queda como columna legada (nunca se expone): se guarda un alias no identificable.
    email = Column(String(255), default="")
    email_hash = Column(String(64), index=True)
    email_enc = Column(Text, default="")
    name = Column(String(255), default="")
    role = Column(String(50), default="candidate")  # candidate|business|admin
    phone = Column(String(50), default="")
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now)
    company = relationship("Company", back_populates="user", uselist=False)
    candidate = relationship("CandidateProfile", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user", cascade="all,delete-orphan")
    otps = relationship("Otp", back_populates="user", cascade="all,delete-orphan")


class Otp(Base):
    __tablename__ = "otps"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    code_hash = Column(String(255))
    expires_at = Column(DateTime)
    attempts = Column(Integer, default=0)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    user = relationship("User", back_populates="otps")


class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    name = Column(String(255), default="")
    ruc = Column(String(20), default="")
    sector = Column(String(100), default="")
    description = Column(Text, default="")
    address = Column(String(255), default="")
    district = Column(String(100), default="Piura")
    city = Column(String(100), default="Piura")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    phone = Column(String(50), default="")
    email = Column(String(255), default="")
    website = Column(String(255), default="")
    logo_url = Column(String(500), default="")
    cover_url = Column(String(500), default="")
    is_public = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    user = relationship("User", back_populates="company")
    jobs = relationship("Job", back_populates="company", cascade="all,delete-orphan")


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    headline = Column(String(255), default="")
    summary = Column(Text, default="")
    city = Column(String(100), default="Piura")
    district = Column(String(100), default="Piura")
    phone = Column(String(50), default="")
    skills = Column(Text, default="")  # comma separated
    avatar_url = Column(String(500), default="")
    cover_url = Column(String(500), default="")
    created_at = Column(DateTime, default=now)
    user = relationship("User", back_populates="candidate")
    items = relationship("ProfileItem", back_populates="profile", cascade="all,delete-orphan")
    photos = relationship("Photo", back_populates="profile", cascade="all,delete-orphan")


class ProfileItem(Base):
    __tablename__ = "profile_items"
    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("candidate_profiles.id"))
    kind = Column(String(50), default="experience")  # experience|education|certification|language|project
    title = Column(String(255), default="")
    org = Column(String(255), default="")
    start = Column(String(20), default="")
    end = Column(String(20), default="")
    description = Column(Text, default="")
    location = Column(String(100), default="")
    profile = relationship("CandidateProfile", back_populates="items")


class Photo(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("candidate_profiles.id"))
    url = Column(String(500), default="")
    caption = Column(String(255), default="")
    kind = Column(String(50), default="gallery")  # avatar|cover|gallery
    profile = relationship("CandidateProfile", back_populates="photos")


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    title = Column(String(255), default="")
    description = Column(Text, default="")
    modality = Column(String(50), default="presencial")  # presencial|remoto|hibrido
    district = Column(String(100), default="Piura")
    city = Column(String(100), default="Piura")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    salary = Column(String(100), default="")
    positions = Column(Integer, default=1)
    status = Column(String(50), default="draft")  # draft|published|closed
    source = Column(String(50), default="manual")  # manual|social|web|seed
    source_url = Column(String(500), default="")
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)
    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job", cascade="all,delete-orphan")
    saves = relationship("SavedJob", back_populates="job", cascade="all,delete-orphan")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_job_candidate"),)
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    candidate_id = Column(Integer, ForeignKey("users.id"))
    message = Column(Text, default="")
    status = Column(String(50), default="applied")  # applied|reviewed|accepted|rejected
    created_at = Column(DateTime, default=now)
    job = relationship("Job", back_populates="applications")
    candidate = relationship("User")


class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_saved"),)
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    candidate_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=now)
    job = relationship("Job", back_populates="saves")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String(50), default="info")
    title = Column(String(255), default="")
    body = Column(Text, default="")
    link = Column(String(255), default="")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    user = relationship("User", back_populates="notifications")


class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), default="")
    email = Column(String(255), default="")
    phone = Column(String(50), default="")
    message = Column(Text, default="")
    type = Column(String(50), default="contact")  # contact|business|candidate|support
    status = Column(String(50), default="new")  # new|contacted|closed
    created_at = Column(DateTime, default=now)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    kind = Column(String(100), default="")
    payload = Column(Text, default="")
    created_at = Column(DateTime, default=now)


def log_event(db, kind, payload=""):
    db.add(Event(kind=kind, payload=str(payload)[:2000]))
