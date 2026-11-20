"""E2E de PrácticaPE v2 contra la instancia de prueba.

Recorre el contrato de pantallas: cada control visible tiene su endpoint y su
estado de error. Imprime PASS/FAIL y un conteo final.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("PP_BASE", "http://127.0.0.1:8096")
SUF = os.getenv("PP_SUF", "")  # sufijo unico por corrida (evita el limite de OTP)
PASS = 0
FAIL = 0
ERRORES = []


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw}
    except Exception as e:
        return 0, {"detail": str(e)}


def ok(nombre, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS  %s %s" % (nombre, extra))
    else:
        FAIL += 1
        ERRORES.append(nombre)
        print("  FAIL  %s %s" % (nombre, extra))


def login(email, role="candidate"):
    st, r = call("POST", "/auth/request-otp", {"email": email, "role": role})
    if st != 200:
        return None
    st, t = call("POST", "/auth/verify-otp", {"email": email, "code": r.get("dev_code", "")})
    return t.get("access_token") if st == 200 else None


CAND_EMAIL = "e2e-cand%s@unp.edu.pe" % SUF
BIZ_EMAIL = "e2e-biz%s@unp.edu.pe" % SUF
ADMIN_EMAIL = "admin%s@practicape.pe" % SUF


def main():
    print("== 1. Publico (home / ofertas / detalle / mapa / empresas)")
    st, h = call("GET", "/health")
    ok("health", st == 200 and h.get("status") == "ok")

    st, d = call("GET", "/jobs?limit=6")
    ok("ofertas home (6)", st == 200 and d.get("total", 0) >= 6, "total=%s" % d.get("total"))
    items = d.get("items", [])
    ok("ofertas sin borradores", all(j["status"] == "published" for j in items))
    ok("ofertas con empresa", all(j.get("company_name") for j in items))
    ok("ofertas con geo", all("lat" in j and "lng" in j for j in items))
    ok("sin campos internos", not any("source_url" in j or "company_id" in j for j in items))

    st, f = call("GET", "/jobs?q=administrativo&district=Piura")
    ok("filtro palabra+distrito", st == 200 and isinstance(f.get("items"), list))
    st, f2 = call("GET", "/jobs?district=NOEXISTE")
    ok("filtro sin resultados", st == 200 and f2.get("total") == 0)

    st, dr = call("GET", "/jobs?status=draft")
    ok("borradores no se filtran", st == 200 and all(j["status"] == "published" for j in dr.get("items", [])))
    st, cl = call("GET", "/jobs?status=closed")
    ok("cerradas no se filtran", st == 200 and all(j["status"] == "published" for j in cl.get("items", [])))

    st, j = call("GET", "/jobs/1")
    ok("detalle de oferta", st == 200 and j.get("title"))

    st, mp = call("GET", "/jobs/map?limit=50")
    ok("mapa con pines", st == 200 and len(mp.get("items", [])) >= 5, "pines=%s" % len(mp.get("items", [])))

    st, ds = call("GET", "/jobs/districts")
    ok("distritos", st == 200 and "Piura" in (ds.get("districts") or []))

    st, cs = call("GET", "/companies")
    ok("directorio de empresas", st == 200 and cs.get("total", 0) >= 5)
    ok("empresas sin email", all("email" not in c for c in cs.get("items", [])))
    st, c1 = call("GET", "/companies/%s" % cs["items"][0]["id"])
    ok("ficha de empresa", st == 200 and isinstance(c1.get("jobs"), list))

    st, p = call("GET", "/profiles/1")
    ok("perfil publico", st == 200 and "name" in p)
    ok("perfil publico sin email", "email" not in p)

    print("== 2. Acceso OTP")
    st, r = call("POST", "/auth/request-otp", {"email": CAND_EMAIL, "role": "candidate"})
    ok("solicitar codigo", st == 200 and r.get("ok"))
    code = r.get("dev_code") or ""
    ok("codigo de 6 digitos", len(code) == 6 and code.isdigit())
    st, bad = call("POST", "/auth/verify-otp", {"email": CAND_EMAIL, "code": "000000"})
    ok("codigo incorrecto", st == 400)
    st, tok = call("POST", "/auth/verify-otp", {"email": CAND_EMAIL, "code": code})
    ok("codigo correcto", st == 200 and tok.get("access_token"))
    CAND = tok.get("access_token")
    st, me = call("GET", "/auth/me", token=CAND)
    ok("sesion /auth/me", st == 200 and me.get("role") == "candidate")
    ok("email real (no alias)", (me.get("email") or "").endswith("@unp.edu.pe"))

    st, tokb = call("POST", "/auth/verify-otp", {"email": BIZ_EMAIL,
                                                "code": call("POST", "/auth/request-otp",
                                                             {"email": BIZ_EMAIL, "role": "business"})[1].get("dev_code", "")})
    ok("cuenta de empresa", st == 200 and tokb.get("user", {}).get("role") == "business")
    BIZ = tokb.get("access_token")

    print("== 3. Candidato: perfil y postulacion")
    st, prof = call("GET", "/me/profile", token=CAND)
    ok("mi perfil", st == 200)
    st, prof2 = call("PUT", "/me/profile", {"headline": "Derecho · egresado", "summary": "Practica en Piura",
                                            "district": "Castilla", "skills": ["Redaccion", "Excel"]}, token=CAND)
    ok("guardar perfil", st == 200 and prof2.get("headline", "").startswith("Derecho"))
    ok("skills en lista", isinstance(prof2.get("skills"), list) and len(prof2.get("skills", [])) == 2)

    st, it = call("POST", "/me/profile/items", {"kind": "experience", "title": "Auxiliar legal",
                                                "org": "Estudio Piura", "start": "2025"}, token=CAND)
    ok("aniadir item", st == 200 and it.get("id"))
    st, dl = call("DELETE", "/me/profile/items/%s" % it["id"], token=CAND)
    ok("borrar item", st == 200 and dl.get("ok"))

    st, ap = call("POST", "/jobs/3/apply", {}, token=CAND)
    ok("postularse", st in (200, 409), "status=%s" % st)
    st, ap2 = call("POST", "/jobs/3/apply", {}, token=CAND)
    ok("postulacion unica", st == 409)
    st, st2 = call("GET", "/jobs/3", token=CAND)
    ok("detalle muestra mi postulacion", (st2.get("my_application") or {}).get("status") == "applied")
    st, mine = call("GET", "/me/applications", token=CAND)
    ok("mis postulaciones", st == 200 and len(mine.get("items", [])) >= 1)
    st, anon = call("POST", "/jobs/2/apply", {})
    ok("postular sin sesion", st in (401, 403))

    print("== 4. Empresa")
    st, bp = call("GET", "/business/profile", token=BIZ)
    ok("perfil de empresa", st == 200)
    st, bp2 = call("PUT", "/business/profile", {"name": "E2E Hosteleria SAC", "sector": "Hosteleria",
                                               "district": "Piura", "description": "Empresa de prueba."}, token=BIZ)
    ok("guardar empresa", st == 200 and bp2.get("name") == "E2E Hosteleria SAC")
    st, nj = call("POST", "/jobs", {"title": "Practicante de cocina", "description": "Apoyo en cocina.",
                                    "category": "Gastronomia", "district": "Piura", "salary": "S/ 930"}, token=BIZ)
    ok("publicar oferta", st == 200 and nj.get("id"))
    JOB = nj["id"]
    st, bj = call("GET", "/business/jobs", token=BIZ)
    ok("ofertas de la empresa", st == 200 and any(j["id"] == JOB for j in bj.get("items", [])))
    st, db2 = call("GET", "/business/dashboard", token=BIZ)
    ok("dashboard empresa", st == 200 and "published" in db2)
    st, put = call("PUT", "/jobs/%s" % JOB, {"title": "Practicante de cocina (actualizado)"}, token=BIZ)
    ok("editar oferta", st == 200 and put.get("title", "").endswith("(actualizado)"))
    st, cl = call("POST", "/jobs/%s/close" % JOB, token=BIZ)
    ok("cerrar oferta", st == 200 and cl.get("status") == "closed")
    st, gone = call("GET", "/jobs/%s" % JOB)
    ok("oferta cerrada no visible", st == 404)

    print("== 5. Admin")
    toka = login(ADMIN_EMAIL, "candidate")
    ok("token admin", bool(toka))
    st, ad = call("GET", "/admin/dashboard", token=toka)
    ok("dashboard admin", st == 200 and ad.get("users", 0) > 0, "users=%s" % ad.get("users"))
    st, u2 = call("GET", "/admin/users", token=toka)
    ok("usuarios admin", st == 200 and u2.get("items"))
    ok("usuarios sin email", all("email" not in x for x in u2.get("items", [])))
    st, l = call("GET", "/admin/leads", token=toka)
    ok("leads admin", st == 200 and "items" in l)
    st, q = call("GET", "/admin/queue", token=toka)
    ok("cola de moderacion", st == 200 and "items" in q)
    st, no = call("GET", "/admin/dashboard", token=CAND)
    ok("admin solo para admin", st == 403)
    st, no2 = call("GET", "/admin/dashboard")
    ok("admin sin token", st == 401)

    print("== 6. Contacto y limites")
    body_intake = {"name": "Empresa X", "email": "x@y.pe",
                   "message": "Quiero publicar vacantes de practica."}
    st, i = call("POST", "/intake", body_intake)
    ok("intake de contacto", st in (200, 429), "status=%s" % st)
    st, i2 = call("POST", "/intake", body_intake)
    ok("intake anti-duplicado", st == 429)

    st, r = call("POST", "/auth/request-otp", {"email": CAND_EMAIL, "role": "candidate"})
    st, r2 = call("POST", "/auth/request-otp", {"email": CAND_EMAIL, "role": "candidate"})
    st, r3 = call("POST", "/auth/request-otp", {"email": CAND_EMAIL, "role": "candidate"})
    ok("OTP limitado por email", st == 429, "status=%s" % st)

    st, j = call("GET", "/jobs/999999")
    ok("oferta inexistente 404", st == 404)

    print()
    print("RESULTADO: %d PASS, %d FAIL" % (PASS, FAIL))
    if ERRORES:
        print("Fallos: " + ", ".join(ERRORES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
