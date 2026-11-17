# app/services/auth_service.py

from app.repositories import user_repository
from app.utils.security import hash_password, verify_password
from app.utils.jwt_utils import generate_token


def register(nombre, email, password, rol="usuario"):
    # La ruta publica /register nunca pasa "rol"; el parametro existe solo
    # para scripts internos (p. ej. crear el primer admin).
    if not nombre or not email or not password:
        raise ValueError("nombre, email y password son obligatorios")

    if user_repository.get_by_email(email):
        raise ValueError("El email ya esta registrado")

    hashed = hash_password(password)
    new_id = user_repository.create(nombre, email, hashed, rol)
    return user_repository.get_by_id(new_id)


def login(email, password):
    usuario = user_repository.get_by_email(email)
    if not usuario or not verify_password(password, usuario["password"]):
        raise ValueError("Credenciales invalidas")

    token = generate_token(usuario)
    usuario.pop("password", None)
    return token, usuario
