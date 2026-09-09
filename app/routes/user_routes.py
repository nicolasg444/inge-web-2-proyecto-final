# app/routes/user_routes.py

from flask import Blueprint, request, jsonify

from app.services import user_service
from app.utils.jwt_utils import token_required

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@users_bp.route("/", methods=["GET"])
@token_required
def listar():
    return jsonify(user_service.listar()), 200


@users_bp.route("/<int:user_id>", methods=["GET"])
@token_required
def obtener(user_id):
    try:
        return jsonify(user_service.obtener(user_id)), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@users_bp.route("/<int:user_id>", methods=["PUT"])
@token_required
def actualizar(user_id):
    data = request.get_json(silent=True) or {}
    try:
        usuario = user_service.actualizar(
            user_id,
            data.get("nombre"),
            data.get("email"),
            data.get("rol", "usuario"),
        )
        return jsonify(usuario), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@token_required
def eliminar(user_id):
    try:
        user_service.eliminar(user_id)
        return jsonify({"mensaje": "Usuario eliminado"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
