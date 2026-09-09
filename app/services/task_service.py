# app/services/task_service.py

from app.repositories import task_repository


def listar():
    return task_repository.get_all()


def obtener(task_id):
    tarea = task_repository.get_by_id(task_id)
    if not tarea:
        raise ValueError("Tarea no encontrada")
    return tarea


def crear(titulo, descripcion, estado, proyecto_id, asignado_a):
    if not titulo:
        raise ValueError("El titulo es obligatorio")
    new_id = task_repository.create(
        titulo, descripcion, estado or "pendiente", proyecto_id, asignado_a
    )
    return task_repository.get_by_id(new_id)


def actualizar(task_id, titulo, descripcion, estado, asignado_a):
    if not task_repository.get_by_id(task_id):
        raise ValueError("Tarea no encontrada")
    task_repository.update(task_id, titulo, descripcion, estado, asignado_a)
    return task_repository.get_by_id(task_id)


def eliminar(task_id):
    if not task_repository.get_by_id(task_id):
        raise ValueError("Tarea no encontrada")
    task_repository.delete(task_id)
