# app/routes/task_routes.py

from flask import Blueprint, request, jsonify

from app import cache
from app.services import task_service
from app.utils.jwt_utils import token_required

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("", methods=["GET"])
@tasks_bp.route("/", methods=["GET"])
@token_required
def listar():
    # Listado global cacheado en Redis (ver app/cache.py).
    return cache.listado_cacheado("tareas", task_service.listar)


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@token_required
def obtener(task_id):
    try:
        return jsonify(task_service.obtener(task_id)), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@tasks_bp.route("", methods=["POST"])
@tasks_bp.route("/", methods=["POST"])
@token_required
def crear():
    data = request.get_json(silent=True) or {}
    try:
        tarea = task_service.crear(
            data.get("titulo"),
            data.get("descripcion"),
            data.get("estado"),
            data.get("proyecto_id"),
            data.get("asignado_a"),
        )
        cache.invalidar("tareas")
        return jsonify(tarea), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@token_required
def actualizar(task_id):
    data = request.get_json(silent=True) or {}
    try:
        tarea = task_service.actualizar(
            task_id,
            data.get("titulo"),
            data.get("descripcion"),
            data.get("estado"),
            data.get("asignado_a"),
        )
        cache.invalidar("tareas")
        return jsonify(tarea), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@token_required
def eliminar(task_id):
    try:
        task_service.eliminar(task_id)
        cache.invalidar("tareas")
        return jsonify({"mensaje": "Tarea eliminada"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
