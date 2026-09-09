# app/services/project_service.py

from app.repositories import project_repository


def listar():
    return project_repository.get_all()


def obtener(project_id):
    proyecto = project_repository.get_by_id(project_id)
    if not proyecto:
        raise ValueError("Proyecto no encontrado")
    return proyecto


def crear(nombre, descripcion, propietario_id):
    if not nombre:
        raise ValueError("El nombre es obligatorio")
    new_id = project_repository.create(nombre, descripcion, propietario_id)
    return project_repository.get_by_id(new_id)


def actualizar(project_id, nombre, descripcion):
    if not project_repository.get_by_id(project_id):
        raise ValueError("Proyecto no encontrado")
    project_repository.update(project_id, nombre, descripcion)
    return project_repository.get_by_id(project_id)


def eliminar(project_id):
    if not project_repository.get_by_id(project_id):
        raise ValueError("Proyecto no encontrado")
    project_repository.delete(project_id)
