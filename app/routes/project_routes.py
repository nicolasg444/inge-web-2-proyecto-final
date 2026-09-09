# app/routes/project_routes.py

from flask import Blueprint, request, jsonify

from app.services import project_service
from app.utils.jwt_utils import token_required

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("", methods=["GET"])
@projects_bp.route("/", methods=["GET"])
@token_required
def listar():
    return jsonify(project_service.listar()), 200


@projects_bp.route("/<int:project_id>", methods=["GET"])
@token_required
def obtener(project_id):
    try:
        return jsonify(project_service.obtener(project_id)), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@projects_bp.route("", methods=["POST"])
@projects_bp.route("/", methods=["POST"])
@token_required
def crear():
    data = request.get_json(silent=True) or {}
    try:
        propietario = int(request.usuario_actual["sub"])
        proyecto = project_service.crear(
            data.get("nombre"),
            data.get("descripcion"),
            data.get("propietario_id", propietario),
        )
        return jsonify(proyecto), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@projects_bp.route("/<int:project_id>", methods=["PUT"])
@token_required
def actualizar(project_id):
    data = request.get_json(silent=True) or {}
    try:
        proyecto = project_service.actualizar(
            project_id, data.get("nombre"), data.get("descripcion")
        )
        return jsonify(proyecto), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
@token_required
def eliminar(project_id):
    try:
        project_service.eliminar(project_id)
        return jsonify({"mensaje": "Proyecto eliminado"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
