# app/utils/jwt_utils.py

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import request, jsonify

from app.config import Config


def generate_token(usuario):
    payload = {
        "sub": str(usuario["id"]),
        "email": usuario["email"],
        "rol": usuario.get("rol", "usuario"),
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=Config.JWT_EXP_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])


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
            return jsonify({"error": "Token invalido"}), 401

        request.usuario_actual = payload
        return f(*args, **kwargs)

    return decorated
