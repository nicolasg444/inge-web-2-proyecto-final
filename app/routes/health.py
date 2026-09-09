# app/routes/health.py
"""Ruta de verificacion de estado (health check) del backend."""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    """Devuelve el estado del servicio."""
    return jsonify({"status": "ok"}), 200


@health_bp.route("/api/health")
def api_health():
    """Alias de /health bajo el prefijo /api."""
    return jsonify({"status": "ok"}), 200
