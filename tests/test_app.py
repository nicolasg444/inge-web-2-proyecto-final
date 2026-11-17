# tests/test_app.py
import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import cache
from app.config import Config, ErrorConfiguracion, leer_secreto


def _b64(datos):
    crudo = json.dumps(datos).encode()
    return base64.urlsafe_b64encode(crudo).rstrip(b"=").decode()


def _token(**cambios):
    ahora = datetime.now(timezone.utc)
    payload = {"sub": "1", "email": "a@b.c", "rol": "usuario",
               "iat": ahora, "exp": ahora + timedelta(hours=1)}
    payload.update(cambios)
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")


def _con(token):
    return {"Authorization": f"Bearer {token}"}


# --- Fase 1: configuracion y endpoints publicos ---------------------------

def test_health_no_requiere_token(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["estado"] == "ok"


def test_quien_devuelve_pod_y_version(client):
    datos = client.get("/quien").get_json()
    assert datos["pod"] and datos["version"]


def test_leer_secreto_prefiere_archivo(tmp_path, monkeypatch):
    archivo = tmp_path / "s.txt"
    archivo.write_text("desde-archivo\n", encoding="utf-8")
    monkeypatch.setenv("PRUEBA_FILE", str(archivo))
    monkeypatch.setenv("PRUEBA", "desde-variable")
    assert leer_secreto("PRUEBA") == "desde-archivo"


def test_leer_secreto_falla_si_falta(monkeypatch):
    monkeypatch.delenv("NO_EXISTE", raising=False)
    monkeypatch.delenv("NO_EXISTE_FILE", raising=False)
    with pytest.raises(ErrorConfiguracion):
        leer_secreto("NO_EXISTE")


def test_leer_secreto_exige_largo_y_rechaza_ejemplo(monkeypatch):
    monkeypatch.setenv("CORTO", "abc")
    with pytest.raises(ErrorConfiguracion):
        leer_secreto("CORTO", min_largo=32)
    monkeypatch.setenv("PUBLICO", "cambia-esta-clave-secreta-en-produccion")
    with pytest.raises(ErrorConfiguracion):
        leer_secreto("PUBLICO", min_largo=32)


def test_error_no_revela_el_valor(monkeypatch):
    monkeypatch.setenv("CORTO", "valor-secreto")
    with pytest.raises(ErrorConfiguracion) as error:
        leer_secreto("CORTO", min_largo=32)
    assert "valor-secreto" not in str(error.value)


# --- Fase 2: JWT ------------------------------------------------------------

@pytest.mark.parametrize("cabecera", [None, "Bearer ", "Basic abc"])
def test_sin_token_401(client, cabecera):
    headers = {"Authorization": cabecera} if cabecera else {}
    r = client.post("/api/proyectos", json={}, headers=headers)
    assert r.status_code == 401


def test_firma_alterada_401(client):
    cabeza, cuerpo, firma = _token().split(".")
    otra = "A" if firma[0] != "A" else "B"
    r = client.get("/api/proyectos", headers=_con(f"{cabeza}.{cuerpo}.{otra}{firma[1:]}"))
    assert r.status_code == 401


def test_payload_alterado_401(client):
    cabeza, _, firma = _token().split(".")
    falso = _b64({"sub": "1", "rol": "admin", "iat": 1, "exp": 9999999999})
    r = client.get("/api/proyectos", headers=_con(f"{cabeza}.{falso}.{firma}"))
    assert r.status_code == 401


def test_alg_none_401(client):
    ahora = int(datetime.now(timezone.utc).timestamp())
    cabeza = _b64({"alg": "none", "typ": "JWT"})
    cuerpo = _b64({"sub": "1", "rol": "admin", "iat": ahora, "exp": ahora + 3600})
    r = client.get("/api/proyectos", headers=_con(f"{cabeza}.{cuerpo}."))
    assert r.status_code == 401


def test_otro_algoritmo_401(client):
    ahora = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "1", "iat": ahora, "exp": ahora + timedelta(hours=1)},
                       Config.JWT_SECRET, algorithm="HS512")
    assert client.get("/api/proyectos", headers=_con(token)).status_code == 401


def test_expirado_401(client):
    ahora = datetime.now(timezone.utc)
    token = _token(iat=ahora - timedelta(hours=2), exp=ahora - timedelta(hours=1))
    r = client.get("/api/proyectos", headers=_con(token))
    assert r.status_code == 401
    assert r.get_json()["error"] == "Token expirado"


def test_sin_exp_401(client):
    token = jwt.encode({"sub": "1", "iat": datetime.now(timezone.utc)},
                       Config.JWT_SECRET, algorithm="HS256")
    assert client.get("/api/proyectos", headers=_con(token)).status_code == 401


def test_usuario_no_puede_cambiar_rol(client):
    r = client.put("/api/usuarios/1", json={"rol": "admin"}, headers=_con(_token()))
    assert r.status_code == 403


def test_usuario_no_puede_borrar_a_otro(client):
    assert client.delete("/api/usuarios/2", headers=_con(_token())).status_code == 403


def test_registro_ignora_rol(client, monkeypatch):
    from app.services import auth_service
    recibido = {}

    def falso_register(nombre, email, password, rol="usuario"):
        recibido["rol"] = rol
        return {"id": 1, "nombre": nombre, "email": email, "rol": rol}

    monkeypatch.setattr(auth_service, "register", falso_register)
    client.post("/api/auth/register",
                json={"nombre": "x", "email": "x@x.x", "password": "p", "rol": "admin"})
    assert recibido["rol"] == "usuario"


# --- Cabeceras de seguridad y CORS -------------------------------------------

@pytest.mark.parametrize("ruta", ["/health", "/api/proyectos", "/no-existe"])
def test_cabeceras_seguridad(client, ruta):
    r = client.get(ruta)
    assert r.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_cors_restringido(client):
    r = client.get("/health", headers={"Origin": "https://malicioso.example"})
    assert "Access-Control-Allow-Origin" not in r.headers
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


# --- Fase 5: cache con degradacion ------------------------------------------

def test_cache_caida_no_rompe_la_api(client, monkeypatch):
    """Redis apunta a un puerto cerrado: el listado debe salir de MySQL."""
    from app.services import project_service
    monkeypatch.setattr(Config, "REDIS_HOST", "127.0.0.1")
    monkeypatch.setattr(Config, "REDIS_PORT", 1)
    monkeypatch.setattr(Config, "REDIS_PASSWORD", "x")
    monkeypatch.setattr(cache, "_cliente", None)
    monkeypatch.setattr(cache, "_pausa_hasta", 0.0)
    monkeypatch.setattr(project_service, "listar",
                        lambda: [{"id": 1, "nombre": "<b>x</b>"}])
    r = client.get("/api/proyectos", headers=_con(_token()))
    assert r.status_code == 200
    assert r.get_json() == [{"id": 1, "nombre": "<b>x</b>"}]
    assert r.headers["X-Cache"] == "MISS"
    assert r.mimetype == "application/json"
