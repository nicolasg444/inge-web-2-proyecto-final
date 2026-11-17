# app/routes/user_routes.py

from flask import Blueprint, request, jsonify

from app import cache
from app.services import user_service
from app.utils.jwt_utils import es_admin, token_required

users_bp = Blueprint("users", __name__)


def _puede_modificar(user_id):
    """Solo el propio usuario o un admin. La identidad sale del JWT
    verificado (claim sub), nunca del cuerpo de la peticion."""
    return es_admin() or request.usuario_actual.get("sub") == str(user_id)


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
    if not _puede_modificar(user_id):
        return jsonify({"error": "No autorizado"}), 403
    data = request.get_json(silent=True) or {}
    # Antes, cualquier usuario autenticado podia cambiar el rol de
    # cualquiera (incluido el suyo a "admin"). Ahora solo un admin.
    if "rol" in data and not es_admin():
        return jsonify({"error": "Solo un admin puede cambiar roles"}), 403
    try:
        usuario = user_service.actualizar(
            user_id,
            data.get("nombre"),
            data.get("email"),
            data.get("rol"),
        )
        cache.invalidar("proyectos", "tareas")
        return jsonify(usuario), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@token_required
def eliminar(user_id):
    if not _puede_modificar(user_id):
        return jsonify({"error": "No autorizado"}), 403
    try:
        user_service.eliminar(user_id)
        # Borrar un usuario deja en NULL propietario_id / asignado_a.
        cache.invalidar("proyectos", "tareas")
        return jsonify({"mensaje": "Usuario eliminado"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
