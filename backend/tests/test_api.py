"""
Suite completa de tests para PracticaPE FastAPI backend.

Estrategia:
  - SQLite in-memory por sesión de pytest (fixture session-scoped).
  - Se inyecta OTP_DEV_CODE=1 via env para obtener dev_code en la respuesta.
  - Se reemplaza get_db con la DB de test.
  - El limiter en memoria se resetea antes de cada test que necesite OTP.
  - Nunca se hardcodea un código OTP: siempre se lee de dev_code.
"""

import os

# Env vars BEFORE any app import
os.environ.setdefault("OTP_DEV_CODE", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-practicape-tests-only-1234567890")
os.environ.setdefault("PRACTICAPE_DB", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# App imports
from app.main import app
from app.core.database import Base, get_db
from app.core.limiter import limiter
from app.core.security import create_access_token, email_hash_of, encrypt_email, email_alias
from app.models import (
    User, Otp, Company, CandidateProfile, Job,
    Application, SavedJob, Notification, Lead, ProfileItem,
)

# ---------------------------------------------------------------------------
# DB in-memory fixture
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    limiter.reset()  # reset rate limiter between tests
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(client, email: str, role: str = "candidate", name: str = "Test User") -> dict:
    """Registrar y autenticar usuario, devuelve {'token': ..., 'user': ...}"""
    limiter.reset()
    r = client.post("/auth/request-otp", json={"email": email, "role": role, "name": name})
    assert r.status_code == 200, r.text
    dev_code = r.json().get("dev_code")
    assert dev_code is not None, "dev_code ausente — OTP_DEV_CODE=1 no activo?"

    r2 = client.post("/auth/verify-otp", json={"email": email, "code": dev_code})
    assert r2.status_code == 200, r2.text
    data = r2.json()
    return {"token": data["access_token"], "user": data["user"]}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_job(db, company_id: int, status: str = "published") -> Job:
    job = Job(
        company_id=company_id,
        title="Practicante Contabilidad",
        description="Apoyo en área contable, Piura.",
        category="Contabilidad",
        modality="presencial",
        district="Piura",
        city="Piura",
        salary="S/ 930",
        status=status,
        source="manual",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _make_admin(db, email: str) -> dict:
    """Crea usuario admin directamente en DB y devuelve token."""
    h = email_hash_of(email)
    user = User(
        email=email_alias(0),
        email_hash=h,
        email_enc=encrypt_email(email),
        name="Admin",
        role="admin",
    )
    db.add(user)
    db.flush()
    user.email = email_alias(user.id)
    db.commit()
    token = create_access_token(user.id, "admin")
    return {"token": token, "user": user}


# ===========================================================================
# HEALTH
# ===========================================================================

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_no_auth_needed(self, client):
        # No Authorization header required
        r = client.get("/health")
        assert r.status_code == 200


# ===========================================================================
# AUTH: request-otp
# ===========================================================================

class TestRequestOtp:
    def test_request_otp_candidate(self, client):
        r = client.post("/auth/request-otp", json={"email": "cand@test.com", "role": "candidate"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "dev_code" in body, "OTP_DEV_CODE=1 debe devolver dev_code"
        assert body["email"] == "cand@test.com"

    def test_request_otp_business(self, client):
        r = client.post("/auth/request-otp", json={
            "email": "biz@test.com", "role": "business", "name": "Empresa Test"
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_request_otp_invalid_email(self, client):
        r = client.post("/auth/request-otp", json={"email": "not-an-email", "role": "candidate"})
        assert r.status_code == 422

    def test_request_otp_missing_email(self, client):
        r = client.post("/auth/request-otp", json={"role": "candidate"})
        assert r.status_code == 422

    def test_request_otp_idempotent_same_user(self, client, db):
        """Dos requests de OTP al mismo email reutilizan el usuario."""
        limiter.reset()
        r1 = client.post("/auth/request-otp", json={"email": "idm@test.com", "role": "candidate"})
        limiter.reset()
        r2 = client.post("/auth/request-otp", json={"email": "idm@test.com", "role": "candidate"})
        assert r1.json()["user_id"] == r2.json()["user_id"]

    def test_request_otp_rate_limit(self, client):
        """Después de 3 requests sin reset, el 4to desde el mismo email debe devolver 429."""
        email = "ratelimited@test.com"
        # El limiter ya fue reseteado por el fixture client; hacemos 3 requests sin reset adicional
        for _ in range(3):
            client.post("/auth/request-otp", json={"email": email, "role": "candidate"})
        # El 4to debe ser bloqueado por otp_max_per_email_window=3
        r = client.post("/auth/request-otp", json={"email": email, "role": "candidate"})
        assert r.status_code == 429


# ===========================================================================
# AUTH: verify-otp
# ===========================================================================

class TestVerifyOtp:
    def test_verify_otp_success_candidate(self, client):
        r1 = client.post("/auth/request-otp", json={"email": "v1@test.com", "role": "candidate"})
        code = r1.json()["dev_code"]
        r2 = client.post("/auth/verify-otp", json={"email": "v1@test.com", "code": code})
        assert r2.status_code == 200
        body = r2.json()
        assert "access_token" in body
        assert body["user"]["role"] == "candidate"
        assert body["user"]["email"] == "v1@test.com"

    def test_verify_otp_success_business(self, client):
        r1 = client.post("/auth/request-otp", json={"email": "b1@test.com", "role": "business", "name": "BizCo"})
        code = r1.json()["dev_code"]
        r2 = client.post("/auth/verify-otp", json={"email": "b1@test.com", "code": code})
        assert r2.status_code == 200
        assert r2.json()["user"]["role"] == "business"

    def test_verify_otp_wrong_code(self, client):
        r1 = client.post("/auth/request-otp", json={"email": "w1@test.com", "role": "candidate"})
        assert r1.status_code == 200
        r2 = client.post("/auth/verify-otp", json={"email": "w1@test.com", "code": "000001"})
        assert r2.status_code == 400

    def test_verify_otp_no_prior_request(self, client):
        r = client.post("/auth/verify-otp", json={"email": "ghost@test.com", "code": "123456"})
        assert r.status_code == 400

    def test_verify_otp_used_once(self, client):
        """El OTP solo puede usarse una vez."""
        r1 = client.post("/auth/request-otp", json={"email": "once@test.com", "role": "candidate"})
        code = r1.json()["dev_code"]
        r2 = client.post("/auth/verify-otp", json={"email": "once@test.com", "code": code})
        assert r2.status_code == 200
        r3 = client.post("/auth/verify-otp", json={"email": "once@test.com", "code": code})
        assert r3.status_code in (400, 429)  # used=True → no otp encontrado

    def test_verify_otp_max_attempts(self, client, db):
        """5 intentos incorrectos seguidos → 429."""
        r1 = client.post("/auth/request-otp", json={"email": "maxattempts@test.com", "role": "candidate"})
        assert r1.status_code == 200
        final_status = None
        for _ in range(6):
            r = client.post("/auth/verify-otp", json={"email": "maxattempts@test.com", "code": "111111"})
            final_status = r.status_code
        assert final_status == 429


# ===========================================================================
# AUTH: /auth/me
# ===========================================================================

class TestAuthMe:
    def test_me_authenticated(self, client):
        auth = _register(client, "me1@test.com")
        r = client.get("/auth/me", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "me1@test.com"
        assert body["role"] == "candidate"

    def test_me_no_token(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_me_invalid_token(self, client):
        r = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401

    def test_me_malformed_header(self, client):
        r = client.get("/auth/me", headers={"Authorization": "Token abc123"})
        assert r.status_code == 401


# ===========================================================================
# JOBS: listado público
# ===========================================================================

class TestJobsList:
    def test_list_jobs_public(self, client, db):
        comp_user = User(
            email="u0@oculto.local", email_hash=email_hash_of("biz_list@test.com"),
            email_enc=encrypt_email("biz_list@test.com"), name="Empresa", role="business"
        )
        db.add(comp_user)
        db.flush()
        comp_user.email = email_alias(comp_user.id)
        comp = Company(user_id=comp_user.id, name="TestCo", is_public=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)
        _seed_job(db, comp.id, "published")
        _seed_job(db, comp.id, "draft")

        r = client.get("/jobs")
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "total" in body
        # Solo publicados visibles sin auth
        for item in body["items"]:
            assert item["status"] == "published"

    def test_list_jobs_filter_by_district(self, client, db):
        r = client.get("/jobs?district=Piura")
        assert r.status_code == 200

    def test_list_jobs_filter_by_modality(self, client, db):
        r = client.get("/jobs?modality=remoto")
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["modality"] == "remoto"

    def test_list_jobs_pagination(self, client):
        r = client.get("/jobs?limit=5&offset=0")
        assert r.status_code == 200

    def test_list_jobs_limit_max(self, client):
        r = client.get("/jobs?limit=101")
        assert r.status_code == 422

    def test_list_jobs_search(self, client):
        r = client.get("/jobs?q=contabilidad")
        assert r.status_code == 200


# ===========================================================================
# JOBS: detalle
# ===========================================================================

class TestJobDetail:
    def _make_published_job(self, db) -> Job:
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of("biz_detail@test.com"),
            email_enc=encrypt_email("biz_detail@test.com"),
            name="BizDetail", role="business"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        c = Company(user_id=u.id, name="DetailCo")
        db.add(c)
        db.commit()
        db.refresh(c)
        return _seed_job(db, c.id, "published")

    def test_get_job_public(self, client, db):
        job = self._make_published_job(db)
        r = client.get(f"/jobs/{job.id}")
        assert r.status_code == 200
        assert r.json()["id"] == job.id

    def test_get_job_not_found(self, client):
        r = client.get("/jobs/999999")
        assert r.status_code == 404

    def test_get_draft_job_anonymous_404(self, client, db):
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of("biz_draft@test.com"),
            email_enc=encrypt_email("biz_draft@test.com"),
            name="BizDraft", role="business"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        c = Company(user_id=u.id, name="DraftCo")
        db.add(c)
        db.commit()
        db.refresh(c)
        job = _seed_job(db, c.id, "draft")
        r = client.get(f"/jobs/{job.id}")
        assert r.status_code == 404

    def test_get_job_candidate_sees_application_field(self, client, db):
        job = self._make_published_job(db)
        auth = _register(client, "cand_det@test.com", "candidate")
        r = client.get(f"/jobs/{job.id}", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        body = r.json()
        assert "my_application" in body


# ===========================================================================
# JOBS: apply
# ===========================================================================

class TestJobApply:
    def _setup(self, client, db):
        """Crea empresa, job published, retorna (job, candidate_token)."""
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of("biz_apply@test.com"),
            email_enc=encrypt_email("biz_apply@test.com"),
            name="BizApply", role="business"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        c = Company(user_id=u.id, name="ApplyCo")
        db.add(c)
        db.commit()
        db.refresh(c)
        job = _seed_job(db, c.id, "published")
        auth = _register(client, "cand_apply@test.com", "candidate")
        return job, auth["token"]

    def test_apply_success(self, client, db):
        job, token = self._setup(client, db)
        r = client.post(f"/jobs/{job.id}/apply", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert "application_id" in r.json()

    def test_apply_duplicate(self, client, db):
        job, token = self._setup(client, db)
        client.post(f"/jobs/{job.id}/apply", headers=auth_headers(token))
        r = client.post(f"/jobs/{job.id}/apply", headers=auth_headers(token))
        assert r.status_code == 409

    def test_apply_no_auth(self, client, db):
        job, _ = self._setup(client, db)
        r = client.post(f"/jobs/{job.id}/apply")
        assert r.status_code == 401

    def test_apply_business_role_forbidden(self, client, db):
        job, _ = self._setup(client, db)
        biz_auth = _register(client, "biz_cant_apply@test.com", "business")
        r = client.post(f"/jobs/{job.id}/apply", headers=auth_headers(biz_auth["token"]))
        assert r.status_code == 403

    def test_apply_draft_job_not_found(self, client, db):
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of("biz_draft2@test.com"),
            email_enc=encrypt_email("biz_draft2@test.com"),
            name="BizDraft2", role="business"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        c = Company(user_id=u.id, name="DraftCo2")
        db.add(c)
        db.commit()
        db.refresh(c)
        job = _seed_job(db, c.id, "draft")
        auth = _register(client, "cand_draft@test.com", "candidate")
        r = client.post(f"/jobs/{job.id}/apply", headers=auth_headers(auth["token"]))
        assert r.status_code == 404  # candidato no ve drafts

    def test_apply_nonexistent_job(self, client):
        auth = _register(client, "cand_ghost@test.com", "candidate")
        r = client.post("/jobs/999999/apply", headers=auth_headers(auth["token"]))
        assert r.status_code == 404


# ===========================================================================
# JOBS: save / unsave
# ===========================================================================

class TestJobSave:
    def _setup(self, client, db):
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of("biz_save@test.com"),
            email_enc=encrypt_email("biz_save@test.com"),
            name="BizSave", role="business"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        c = Company(user_id=u.id, name="SaveCo")
        db.add(c)
        db.commit()
        db.refresh(c)
        job = _seed_job(db, c.id, "published")
        auth = _register(client, "cand_save@test.com", "candidate")
        return job, auth["token"]

    def test_save_job(self, client, db):
        job, token = self._setup(client, db)
        r = client.post(f"/jobs/{job.id}/save", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["saved"] is True

    def test_save_already_saved_idempotent(self, client, db):
        job, token = self._setup(client, db)
        client.post(f"/jobs/{job.id}/save", headers=auth_headers(token))
        r = client.post(f"/jobs/{job.id}/save", headers=auth_headers(token))
        assert r.status_code == 200

    def test_unsave_job(self, client, db):
        job, token = self._setup(client, db)
        client.post(f"/jobs/{job.id}/save", headers=auth_headers(token))
        r = client.delete(f"/jobs/{job.id}/save", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["saved"] is False

    def test_save_no_auth(self, client, db):
        job, _ = self._setup(client, db)
        r = client.post(f"/jobs/{job.id}/save")
        assert r.status_code == 401

    def test_saved_mine_list(self, client, db):
        job, token = self._setup(client, db)
        client.post(f"/jobs/{job.id}/save", headers=auth_headers(token))
        r = client.get("/jobs/saved/mine", headers=auth_headers(token))
        assert r.status_code == 200
        ids = [item["id"] for item in r.json()["items"]]
        assert job.id in ids


# ===========================================================================
# JOBS: create / update / close (business)
# ===========================================================================

class TestJobCRUD:
    def _biz_with_company(self, client, db, suffix: str):
        auth = _register(client, f"biz_crud_{suffix}@test.com", "business", "BizCRUD")
        # La empresa se crea automáticamente en auth router al registrarse como business
        user_id = auth["user"]["id"]
        # Ensure company exists
        u = db.query(User).filter(User.id == user_id).first()
        if not u.company:
            c = Company(user_id=user_id, name="CRUD Co")
            db.add(c)
            db.commit()
        return auth

    def test_create_job(self, client, db):
        auth = self._biz_with_company(client, db, "create")
        r = client.post("/jobs", json={
            "title": "Practicante TI",
            "description": "Soporte técnico",
            "category": "TI",
            "modality": "presencial",
            "district": "Piura",
            "salary": "S/ 930",
        }, headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert r.json()["title"] == "Practicante TI"

    def test_create_job_no_title_422(self, client, db):
        auth = self._biz_with_company(client, db, "notitle")
        r = client.post("/jobs", json={
            "title": "",
            "description": "Sin título",
        }, headers=auth_headers(auth["token"]))
        assert r.status_code == 400

    def test_create_job_candidate_forbidden(self, client):
        auth = _register(client, "cand_job@test.com", "candidate")
        r = client.post("/jobs", json={"title": "Hack", "description": "x"}, headers=auth_headers(auth["token"]))
        assert r.status_code == 403

    def test_update_job(self, client, db):
        auth = self._biz_with_company(client, db, "update")
        r_create = client.post("/jobs", json={
            "title": "Original", "description": "Desc", "modality": "presencial",
            "district": "Piura", "status": "draft"
        }, headers=auth_headers(auth["token"]))
        assert r_create.status_code == 200
        job_id = r_create.json()["id"]
        r_update = client.put(f"/jobs/{job_id}", json={"title": "Actualizado"}, headers=auth_headers(auth["token"]))
        assert r_update.status_code == 200
        assert r_update.json()["title"] == "Actualizado"

    def test_close_job(self, client, db):
        auth = self._biz_with_company(client, db, "close")
        r_create = client.post("/jobs", json={
            "title": "Para cerrar", "description": "Desc", "modality": "presencial",
            "district": "Piura", "status": "published"
        }, headers=auth_headers(auth["token"]))
        assert r_create.status_code == 200
        job_id = r_create.json()["id"]
        # Publish it first so _visible works for business owner
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = "published"
        db.commit()
        r_close = client.post(f"/jobs/{job_id}/close", headers=auth_headers(auth["token"]))
        assert r_close.status_code == 200
        assert r_close.json()["status"] == "closed"

    def test_close_other_biz_job_403(self, client, db):
        """Empresa B no puede cerrar job de empresa A."""
        auth_a = self._biz_with_company(client, db, "biza")
        auth_b = self._biz_with_company(client, db, "bizb")
        r_create = client.post("/jobs", json={
            "title": "Job de A", "description": "x", "modality": "presencial",
            "district": "Piura", "status": "published"
        }, headers=auth_headers(auth_a["token"]))
        assert r_create.status_code == 200
        job_id = r_create.json()["id"]
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = "published"
        db.commit()
        r = client.post(f"/jobs/{job_id}/close", headers=auth_headers(auth_b["token"]))
        assert r.status_code == 403


# ===========================================================================
# JOBS: submit (candidate submits a job for review)
# ===========================================================================

class TestJobSubmit:
    def test_submit_text(self, client):
        auth = _register(client, "cand_submit@test.com", "candidate")
        r = client.post("/jobs/submit", json={
            "text": "Empresa busca practicante de administración para área de logística en Piura",
            "title": "Practicante Administración"
        }, headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_submit_no_content_400(self, client):
        auth = _register(client, "cand_submit2@test.com", "candidate")
        r = client.post("/jobs/submit", json={}, headers=auth_headers(auth["token"]))
        assert r.status_code == 400

    def test_submit_no_auth(self, client):
        r = client.post("/jobs/submit", json={"text": "Oferta laboral en Piura para prácticas"})
        assert r.status_code == 401


# ===========================================================================
# JOBS: sources, districts, map
# ===========================================================================

class TestJobMisc:
    def test_job_sources(self, client):
        r = client.get("/jobs/sources")
        assert r.status_code == 200
        assert "sources" in r.json()

    def test_job_districts(self, client):
        r = client.get("/jobs/districts")
        assert r.status_code == 200
        assert "districts" in r.json()
        assert len(r.json()["districts"]) > 0

    def test_job_map(self, client):
        r = client.get("/jobs/map")
        assert r.status_code == 200
        assert "items" in r.json()


# ===========================================================================
# COMPANIES
# ===========================================================================

class TestCompanies:
    def _make_company(self, db, suffix: str, is_public: bool = True) -> Company:
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of(f"biz_co_{suffix}@test.com"),
            email_enc=encrypt_email(f"biz_co_{suffix}@test.com"),
            name=f"Co {suffix}", role="business"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        c = Company(user_id=u.id, name=f"Empresa {suffix}", is_public=is_public)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c

    def test_list_companies(self, client, db):
        self._make_company(db, "list1")
        r = client.get("/companies")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_list_companies_only_public(self, client, db):
        self._make_company(db, "pub", is_public=True)
        self._make_company(db, "priv", is_public=False)
        r = client.get("/companies")
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["is_public"] is True

    def test_get_company_detail(self, client, db):
        c = self._make_company(db, "detail")
        r = client.get(f"/companies/{c.id}")
        assert r.status_code == 200
        assert r.json()["id"] == c.id

    def test_get_company_private_returns_detail_key(self, client, db):
        c = self._make_company(db, "privatedet", is_public=False)
        r = client.get(f"/companies/{c.id}")
        assert r.status_code == 200
        # Private company: returns {"detail": "Empresa no encontrada"}
        assert "detail" in r.json()

    def test_get_company_not_found(self, client):
        r = client.get("/companies/999999")
        assert r.status_code == 200
        assert "detail" in r.json()

    def test_list_companies_search(self, client, db):
        self._make_company(db, "searchme")
        r = client.get("/companies?q=searchme")
        assert r.status_code == 200


# ===========================================================================
# ME: profile (candidate)
# ===========================================================================

class TestMeProfile:
    def test_get_profile(self, client):
        auth = _register(client, "cand_profile@test.com", "candidate")
        r = client.get("/me/profile", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        body = r.json()
        assert "headline" in body
        assert "skills" in body

    def test_get_profile_no_auth(self, client):
        r = client.get("/me/profile")
        assert r.status_code == 401

    def test_update_profile(self, client):
        auth = _register(client, "cand_up@test.com", "candidate")
        r = client.put("/me/profile", json={
            "headline": "Estudiante Contabilidad",
            "summary": "Busco prácticas en Piura",
            "city": "Piura",
            "district": "Piura",
            "phone": "987654321",
            "skills": ["Excel", "Word"],
        }, headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        body = r.json()
        assert body["headline"] == "Estudiante Contabilidad"
        assert "Excel" in body["skills"]

    def test_update_profile_business_role_forbidden(self, client):
        """PUT /me/profile solo para candidatos."""
        auth = _register(client, "biz_profile@test.com", "business")
        r = client.put("/me/profile", json={"headline": "BizProfile"}, headers=auth_headers(auth["token"]))
        assert r.status_code == 403


# ===========================================================================
# ME: profile items
# ===========================================================================

class TestProfileItems:
    def test_add_profile_item(self, client):
        auth = _register(client, "cand_items@test.com", "candidate")
        # Ensure profile exists
        client.get("/me/profile", headers=auth_headers(auth["token"]))
        r = client.post("/me/profile/items", json={
            "kind": "experience",
            "title": "Practicante en Banco",
            "org": "BCP",
            "start": "2023-01",
            "end": "2023-06",
            "description": "Apoyo en cajero",
            "location": "Piura",
        }, headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert "id" in r.json()

    def test_add_item_no_title(self, client):
        auth = _register(client, "cand_notitle@test.com", "candidate")
        client.get("/me/profile", headers=auth_headers(auth["token"]))
        r = client.post("/me/profile/items", json={
            "kind": "education", "title": "", "org": "UNP"
        }, headers=auth_headers(auth["token"]))
        assert r.status_code == 400

    def test_delete_profile_item(self, client):
        auth = _register(client, "cand_del@test.com", "candidate")
        client.get("/me/profile", headers=auth_headers(auth["token"]))
        r_add = client.post("/me/profile/items", json={
            "kind": "experience", "title": "Para borrar", "org": "Co"
        }, headers=auth_headers(auth["token"]))
        item_id = r_add.json()["id"]
        r_del = client.delete(f"/me/profile/items/{item_id}", headers=auth_headers(auth["token"]))
        assert r_del.status_code == 200
        assert r_del.json()["ok"] is True

    def test_delete_item_not_found(self, client):
        auth = _register(client, "cand_del2@test.com", "candidate")
        client.get("/me/profile", headers=auth_headers(auth["token"]))
        r = client.delete("/me/profile/items/999999", headers=auth_headers(auth["token"]))
        assert r.status_code == 404

    def test_delete_other_users_item_404(self, client, db):
        """Un candidato no puede borrar items de otro."""
        auth1 = _register(client, "cand_a_item@test.com", "candidate")
        auth2 = _register(client, "cand_b_item@test.com", "candidate")
        client.get("/me/profile", headers=auth_headers(auth1["token"]))
        r_add = client.post("/me/profile/items", json={
            "kind": "experience", "title": "Item de A", "org": "X"
        }, headers=auth_headers(auth1["token"]))
        item_id = r_add.json()["id"]
        r = client.delete(f"/me/profile/items/{item_id}", headers=auth_headers(auth2["token"]))
        assert r.status_code == 404  # profile de B no tiene ese item


# ===========================================================================
# ME: applications
# ===========================================================================

class TestMeApplications:
    def test_my_applications_empty(self, client):
        auth = _register(client, "cand_myapps@test.com", "candidate")
        r = client.get("/me/applications", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_my_applications_after_apply(self, client, db):
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of("biz_myapps@test.com"),
            email_enc=encrypt_email("biz_myapps@test.com"),
            name="BizApps", role="business"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        c = Company(user_id=u.id, name="AppsCo")
        db.add(c)
        db.commit()
        db.refresh(c)
        job = _seed_job(db, c.id, "published")

        auth = _register(client, "cand_mypps2@test.com", "candidate")
        client.post(f"/jobs/{job.id}/apply", headers=auth_headers(auth["token"]))
        r = client.get("/me/applications", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1
        assert r.json()["items"][0]["job_id"] == job.id

    def test_my_applications_no_auth(self, client):
        r = client.get("/me/applications")
        assert r.status_code == 401


# ===========================================================================
# ME: notifications
# ===========================================================================

class TestMeNotifications:
    def test_notifications_empty(self, client):
        auth = _register(client, "cand_notif@test.com", "candidate")
        r = client.get("/me/notifications", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_mark_notification_read(self, client, db):
        auth = _register(client, "cand_read@test.com", "candidate")
        user_id = auth["user"]["id"]
        notif = Notification(user_id=user_id, type="info", title="Hola", body="Test")
        db.add(notif)
        db.commit()
        r = client.patch(f"/me/notifications/{notif.id}/read", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert r.json()["ok"] is True
        db.refresh(notif)
        assert notif.is_read is True

    def test_mark_nonexistent_notification_ok(self, client):
        """API retorna ok:True incluso si la notif no existe."""
        auth = _register(client, "cand_notif2@test.com", "candidate")
        r = client.patch("/me/notifications/999999/read", headers=auth_headers(auth["token"]))
        assert r.status_code == 200

    def test_notifications_no_auth(self, client):
        r = client.get("/me/notifications")
        assert r.status_code == 401


# ===========================================================================
# BUSINESS
# ===========================================================================

class TestBusiness:
    def test_business_profile_get(self, client):
        auth = _register(client, "biz_bp@test.com", "business", "BizProfile")
        r = client.get("/business/profile", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert "name" in r.json()

    def test_business_profile_update(self, client):
        auth = _register(client, "biz_up@test.com", "business", "BizUpdate")
        r = client.put("/business/profile", json={
            "name": "Mi Empresa SA",
            "ruc": "20123456789",
            "sector": "Tecnología",
            "district": "Piura",
            "city": "Piura",
        }, headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert r.json()["name"] == "Mi Empresa SA"

    def test_business_dashboard(self, client):
        auth = _register(client, "biz_dash@test.com", "business", "BizDash")
        r = client.get("/business/dashboard", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        body = r.json()
        assert "published" in body
        assert "applications" in body

    def test_business_jobs_list(self, client):
        auth = _register(client, "biz_jobs@test.com", "business", "BizJobs")
        r = client.get("/business/jobs", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_business_routes_candidate_forbidden(self, client):
        auth = _register(client, "cand_biz@test.com", "candidate")
        r = client.get("/business/dashboard", headers=auth_headers(auth["token"]))
        assert r.status_code == 403


# ===========================================================================
# ADMIN
# ===========================================================================

class TestAdmin:
    def test_admin_dashboard(self, client, db):
        admin = _make_admin(db, "admin_dash@test.com")
        r = client.get("/admin/dashboard", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        body = r.json()
        assert "users" in body
        assert "jobs_published" in body
        assert "queue" in body

    def test_admin_dashboard_candidate_forbidden(self, client):
        auth = _register(client, "cand_admin@test.com", "candidate")
        r = client.get("/admin/dashboard", headers=auth_headers(auth["token"]))
        assert r.status_code == 403

    def test_admin_dashboard_business_forbidden(self, client):
        auth = _register(client, "biz_admin@test.com", "business")
        r = client.get("/admin/dashboard", headers=auth_headers(auth["token"]))
        assert r.status_code == 403

    def test_admin_queue_empty(self, client, db):
        admin = _make_admin(db, "admin_queue@test.com")
        r = client.get("/admin/queue", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_admin_queue_with_pending(self, client, db):
        admin = _make_admin(db, "admin_queue2@test.com")
        # Create a pending job
        job = Job(title="Pending Job", description="Test", status="pending", source="user")
        db.add(job)
        db.commit()
        r = client.get("/admin/queue", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        ids = [item["id"] for item in r.json()["items"]]
        assert job.id in ids

    def test_admin_approve_job(self, client, db):
        admin = _make_admin(db, "admin_approve@test.com")
        job = Job(title="To Approve", description="Test", status="pending", source="user")
        db.add(job)
        db.commit()
        r = client.patch(f"/admin/queue/{job.id}?action=approve", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        assert r.json()["status"] == "published"

    def test_admin_reject_job(self, client, db):
        admin = _make_admin(db, "admin_reject@test.com")
        job = Job(title="To Reject", description="Test", status="pending", source="user")
        db.add(job)
        db.commit()
        r = client.patch(f"/admin/queue/{job.id}?action=reject", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

    def test_admin_moderate_invalid_action(self, client, db):
        admin = _make_admin(db, "admin_inv@test.com")
        job = Job(title="Job", description="x", status="pending", source="user")
        db.add(job)
        db.commit()
        r = client.patch(f"/admin/queue/{job.id}?action=delete", headers=auth_headers(admin["token"]))
        assert r.status_code == 400

    def test_admin_moderate_not_found(self, client, db):
        admin = _make_admin(db, "admin_404@test.com")
        r = client.patch("/admin/queue/999999?action=approve", headers=auth_headers(admin["token"]))
        assert r.status_code == 404

    def test_admin_users_list(self, client, db):
        admin = _make_admin(db, "admin_users@test.com")
        r = client.get("/admin/users", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_admin_toggle_user_active(self, client, db):
        admin = _make_admin(db, "admin_toggle@test.com")
        # Create a user to toggle
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of("toggle_target@test.com"),
            email_enc=encrypt_email("toggle_target@test.com"),
            name="Target", role="candidate"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        db.commit()
        r = client.patch(f"/admin/users/{u.id}?active=false", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_admin_toggle_user_not_found(self, client, db):
        admin = _make_admin(db, "admin_tnotfound@test.com")
        r = client.patch("/admin/users/999999?active=false", headers=auth_headers(admin["token"]))
        assert r.status_code == 404

    def test_admin_leads(self, client, db):
        admin = _make_admin(db, "admin_leads@test.com")
        r = client.get("/admin/leads", headers=auth_headers(admin["token"]))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_admin_no_auth(self, client):
        r = client.get("/admin/dashboard")
        assert r.status_code == 401


# ===========================================================================
# PUBLIC: intake
# ===========================================================================

class TestIntake:
    def test_intake_success(self, client):
        limiter.reset()
        r = client.post("/intake", json={
            "name": "Juan Pérez",
            "email": "juan@empresa.com",
            "phone": "987000000",
            "message": "Queremos publicar nuestras prácticas en la plataforma.",
            "type": "contact",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert "lead_id" in r.json()

    def test_intake_short_name(self, client):
        limiter.reset()
        r = client.post("/intake", json={
            "name": "Jo",
            "email": "jo@co.com",
            "message": "Mensaje suficientemente largo para el test",
        })
        assert r.status_code == 400

    def test_intake_short_message(self, client):
        limiter.reset()
        r = client.post("/intake", json={
            "name": "Pedro",
            "email": "pedro@co.com",
            "message": "Corto",
        })
        assert r.status_code == 400

    def test_intake_rate_limit(self, client):
        """Segunda petición del mismo IP en <60s → 429."""
        limiter.reset()
        client.post("/intake", json={
            "name": "Maria Lopez",
            "email": "maria@co.com",
            "message": "Primera solicitud válida y bastante larga para pasar el filtro.",
        })
        r = client.post("/intake", json={
            "name": "Maria Lopez",
            "email": "maria@co.com",
            "message": "Segunda solicitud duplicada en la misma ventana.",
        })
        assert r.status_code == 429


# ===========================================================================
# SECURITY: 401 sin token, 403 rol incorrecto
# ===========================================================================

class TestSecurity:
    PROTECTED_ROUTES = [
        ("GET", "/auth/me"),
        ("GET", "/me/profile"),
        ("GET", "/me/applications"),
        ("GET", "/me/notifications"),
        ("GET", "/business/profile"),
        ("GET", "/business/dashboard"),
        ("GET", "/business/jobs"),
        ("GET", "/admin/dashboard"),
        ("GET", "/admin/queue"),
        ("GET", "/admin/users"),
        ("GET", "/admin/leads"),
    ]

    def test_all_protected_routes_require_auth(self, client):
        for method, path in self.PROTECTED_ROUTES:
            r = getattr(client, method.lower())(path)
            assert r.status_code == 401, f"{method} {path} expected 401, got {r.status_code}"

    def test_candidate_cannot_access_admin(self, client):
        auth = _register(client, "cand_sec@test.com", "candidate")
        for _, path in [("GET", "/admin/dashboard"), ("GET", "/admin/queue"), ("GET", "/admin/users")]:
            r = client.get(path, headers=auth_headers(auth["token"]))
            assert r.status_code == 403, f"GET {path} expected 403 for candidate"

    def test_business_cannot_access_admin(self, client):
        auth = _register(client, "biz_sec@test.com", "business")
        r = client.get("/admin/dashboard", headers=auth_headers(auth["token"]))
        assert r.status_code == 403

    def test_candidate_cannot_create_job(self, client):
        auth = _register(client, "cand_job_sec@test.com", "candidate")
        r = client.post("/jobs", json={"title": "Hack"}, headers=auth_headers(auth["token"]))
        assert r.status_code == 403

    def test_candidate_cannot_close_job(self, client, db):
        job = Job(title="Job", description="x", status="published", source="manual")
        db.add(job)
        db.commit()
        auth = _register(client, "cand_close_sec@test.com", "candidate")
        r = client.post(f"/jobs/{job.id}/close", headers=auth_headers(auth["token"]))
        assert r.status_code == 403

    def test_inactive_user_401(self, client, db):
        """Usuario desactivado no puede autenticarse."""
        auth = _register(client, "inactive@test.com", "candidate")
        user_id = auth["user"]["id"]
        user = db.query(User).filter(User.id == user_id).first()
        user.is_active = False
        db.commit()
        r = client.get("/auth/me", headers=auth_headers(auth["token"]))
        assert r.status_code == 401

    def test_expired_token_format_rejected(self, client):
        """Token malformado → 401."""
        r = client.get("/me/profile", headers={"Authorization": "Bearer eyJfake.payload.sig"})
        assert r.status_code == 401

    def test_no_bearer_prefix_401(self, client):
        auth = _register(client, "cand_bearer@test.com", "candidate")
        r = client.get("/auth/me", headers={"Authorization": auth["token"]})
        assert r.status_code == 401


# ===========================================================================
# JOBS: permisos de moderación (applicants)
# ===========================================================================

class TestJobApplicants:
    def test_business_sees_own_applicants(self, client, db):
        biz_auth = _register(client, "biz_app_own@test.com", "business", "BizOwn")
        user = db.query(User).filter(User.id == biz_auth["user"]["id"]).first()
        # Ensure company
        if not user.company:
            c = Company(user_id=user.id, name="OwnCo")
            db.add(c)
            db.commit()
            db.refresh(user)
        r_job = client.post("/jobs", json={
            "title": "Con Postulantes", "description": "x",
            "modality": "presencial", "district": "Piura", "status": "published"
        }, headers=auth_headers(biz_auth["token"]))
        assert r_job.status_code == 200
        job_id = r_job.json()["id"]
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = "published"
        db.commit()

        # Candidate applies
        cand_auth = _register(client, "cand_app_own@test.com", "candidate")
        client.post(f"/jobs/{job_id}/apply", headers=auth_headers(cand_auth["token"]))

        r = client.get(f"/jobs/{job_id}/applicants", headers=auth_headers(biz_auth["token"]))
        assert r.status_code == 200
        assert len(r.json()["items"]) >= 1

    def test_candidate_cannot_see_applicants(self, client, db):
        u = User(
            email="u0@oculto.local",
            email_hash=email_hash_of("biz_appsec@test.com"),
            email_enc=encrypt_email("biz_appsec@test.com"),
            name="BizSec", role="business"
        )
        db.add(u)
        db.flush()
        u.email = email_alias(u.id)
        c = Company(user_id=u.id, name="SecCo")
        db.add(c)
        db.commit()
        db.refresh(c)
        job = _seed_job(db, c.id, "published")

        cand_auth = _register(client, "cand_appsec@test.com", "candidate")
        r = client.get(f"/jobs/{job.id}/applicants", headers=auth_headers(cand_auth["token"]))
        assert r.status_code == 403


# ===========================================================================
# PUBLIC PROFILES
# ===========================================================================

class TestPublicProfiles:
    def test_get_public_profile(self, client, db):
        auth = _register(client, "cand_pub@test.com", "candidate")
        # Ensure profile exists
        client.get("/me/profile", headers=auth_headers(auth["token"]))
        user_id = auth["user"]["id"]
        r = client.get(f"/profiles/{user_id}")
        assert r.status_code == 200
        assert "headline" in r.json()

    def test_get_nonexistent_public_profile(self, client):
        r = client.get("/profiles/999999")
        assert r.status_code == 200
        assert "detail" in r.json()


# ===========================================================================
# JWT token claims
# ===========================================================================

class TestJWT:
    def test_token_contains_valid_role(self, client):
        auth = _register(client, "cand_jwt@test.com", "candidate")
        r = client.get("/auth/me", headers=auth_headers(auth["token"]))
        assert r.status_code == 200
        assert r.json()["role"] == "candidate"

    def test_fabricated_admin_token_rejected(self, client, db):
        """Token con role=admin fabricado para user que no es admin → 403 en rutas de admin."""
        # Create a candidate, then forge a token with role=admin
        auth = _register(client, "cand_forge@test.com", "candidate")
        user_id = auth["user"]["id"]
        fake_token = create_access_token(user_id, "admin")
        # /auth/me will pass (token is valid), but the user in DB has role=candidate
        r_me = client.get("/auth/me", headers=auth_headers(fake_token))
        assert r_me.status_code == 200  # token is valid, user exists
        # Admin dashboard: role-check is done against token's role claim
        r_admin = client.get("/admin/dashboard", headers=auth_headers(fake_token))
        # Depends on implementation: either 403 (DB role) or 200 (token role)
        # In this app, require_role checks user.role from DB via current_user
        # candidate in DB → 403
        assert r_admin.status_code == 403
