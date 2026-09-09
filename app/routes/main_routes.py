# app/routes/main_routes.py

from flask import Blueprint, jsonify

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return jsonify(
        {
            "mensaje": "API Ingenieria Web II funcionando",
            "estado": "ok",
            "endpoints": {
                "auth": ["/api/auth/register", "/api/auth/login"],
                "usuarios": "/api/usuarios",
                "proyectos": "/api/proyectos",
                "tareas": "/api/tareas",
                "health": "/api/health",
            },
        }
    ), 200
