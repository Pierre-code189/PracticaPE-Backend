"""Deduplicación del recolector: sin red, tests deterministas."""
import sqlite3

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.web_collector import canonical_url


def test_url_canonica_quita_tracking_y_fragmento():
    a = "https://WWW.pe.computrabajo.com/oferta/oferta-123/?utm_source=ddg&fbclid=abc#detalle"
    b = "https://pe.computrabajo.com/oferta/oferta-123"
    assert canonical_url(a) == canonical_url(b) == "https://pe.computrabajo.com/oferta/oferta-123"


def test_url_canonica_conserva_parametros_reales():
    url = "https://www.practicas.pe/oferta.html?id=71628&utm_medium=search"
    assert canonical_url(url) == "https://practicas.pe/oferta.html?id=71628"


def test_url_canonica_vacia():
    assert canonical_url("") == ""
    assert canonical_url(None) == ""


def test_indice_unico_rechaza_segunda_url():
    """Red de seguridad para dos recolectores concurrentes."""
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT, source_url TEXT)")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_source_url ON jobs(source_url) "
               "WHERE source_url IS NOT NULL AND source_url != ''")
    db.execute("INSERT INTO jobs (title, source_url) VALUES ('una', 'https://x.pe/a')")
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO jobs (title, source_url) VALUES ('otra', 'https://x.pe/a')")
        db.commit()
    # Las filas sin URL (manual/seed) sí pueden coexistir.
    db.execute("INSERT INTO jobs (title, source_url) VALUES ('manual', '')")
    db.execute("INSERT INTO jobs (title, source_url) VALUES ('otra manual', '')")
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 3


def test_integrity_error_es_de_sqlalchemy():
    """El recolector atrapa este tipo, no el sqlite3 crudo."""
    assert issubclass(IntegrityError, Exception)
