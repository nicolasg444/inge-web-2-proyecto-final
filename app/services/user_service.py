# app/services/user_service.py

from app.repositories import user_repository


def listar():
    return user_repository.get_all()


def obtener(user_id):
    usuario = user_repository.get_by_id(user_id)
    if not usuario:
        raise ValueError("Usuario no encontrado")
    return usuario


def actualizar(user_id, nombre, email, rol=None):
    actual = user_repository.get_by_id(user_id)
    if not actual:
        raise ValueError("Usuario no encontrado")
    # Campos omitidos conservan su valor (antes un PUT sin "rol" degradaba
    # a un admin a "usuario" y uno sin "nombre" lo dejaba en NULL).
    user_repository.update(
        user_id,
        nombre or actual["nombre"],
        email or actual["email"],
        rol or actual["rol"],
    )
    return user_repository.get_by_id(user_id)


def eliminar(user_id):
    if not user_repository.get_by_id(user_id):
        raise ValueError("Usuario no encontrado")
    user_repository.delete(user_id)
