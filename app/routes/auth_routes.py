# app/routes/auth_routes.py

from flask import Blueprint, request, jsonify

from app.services import auth_service

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    try:
        # El rol NO se toma del cuerpo de la peticion: antes cualquiera podia
        # registrarse como "admin". Todo registro publico es "usuario"; un
        # admin existente puede promover a otro con PUT /api/usuarios/<id>.
        usuario = auth_service.register(
            data.get("nombre"),
            data.get("email"),
            data.get("password"),
        )
        return jsonify(usuario), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    try:
        token, usuario = auth_service.login(
            data.get("email"), data.get("password")
        )
        return jsonify({"token": token, "usuario": usuario}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
