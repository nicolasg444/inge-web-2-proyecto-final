# app/utils/jwt_utils.py
"""Emision y verificacion de JWT (HS256, sin estado).

La verificacion no depende de memoria del proceso: cualquier replica que
tenga el mismo JWT_SECRET valida el token. Por eso la API escala
horizontalmente sin sesiones pegajosas.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import request, jsonify

from app.config import Config

# Lista blanca de algoritmos. PyJWT rechaza cualquier otro (incluido "none")
# y compara la firma con hmac.compare_digest (tiempo constante).
ALGORITMOS = ["HS256"]


def generate_token(usuario):
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario["id"]),
        "email": usuario["email"],
        "rol": usuario.get("rol", "usuario"),
        "exp": ahora + timedelta(hours=Config.JWT_EXP_HOURS),
        "iat": ahora,
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")


def decode_token(token):
    return jwt.decode(
        token,
        Config.JWT_SECRET,
        algorithms=ALGORITMOS,
        # Sin exp/iat/sub el token se rechaza: un token sin caducidad
        # seria valido para siempre si se filtra.
        options={"require": ["exp", "iat", "sub"]},
    )


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Token no proporcionado"}), 401

        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            # Firma alterada, alg distinto de HS256, iat en el futuro,
            # claims faltantes o token mal formado.
            return jsonify({"error": "Token invalido"}), 401

        request.usuario_actual = payload
        return f(*args, **kwargs)

    return decorated


def es_admin():
    """True si el usuario del JWT verificado tiene rol admin."""
    return getattr(request, "usuario_actual", {}).get("rol") == "admin"
