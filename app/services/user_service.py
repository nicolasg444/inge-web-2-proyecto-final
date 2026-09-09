# app/services/user_service.py

from app.repositories import user_repository


def listar():
    return user_repository.get_all()


def obtener(user_id):
    usuario = user_repository.get_by_id(user_id)
    if not usuario:
        raise ValueError("Usuario no encontrado")
    return usuario


def actualizar(user_id, nombre, email, rol):
    if not user_repository.get_by_id(user_id):
        raise ValueError("Usuario no encontrado")
    user_repository.update(user_id, nombre, email, rol)
    return user_repository.get_by_id(user_id)


def eliminar(user_id):
    if not user_repository.get_by_id(user_id):
        raise ValueError("Usuario no encontrado")
    user_repository.delete(user_id)
