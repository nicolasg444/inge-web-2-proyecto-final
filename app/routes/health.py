# app/routes/health.py
"""Rutas publicas de estado: /health, /api/health y /quien.

/health NO consulta MySQL ni Redis a proposito: la usan las probes de
Docker y Kubernetes. Si dependiera de un servicio externo, una caida de la
base de datos haria que K8s reiniciara todos los pods de la API sin arreglar
nada (y empeorando la situacion con arranques en cadena).
"""

import os
import socket

from flask import Blueprint, jsonify

from app.config import Config

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    """Devuelve el estado del proceso (liveness)."""
    # "status" se conserva porque el frontend lo lee; "estado" por la guia.
    return jsonify({"status": "ok", "estado": "ok"}), 200


@health_bp.route("/api/health")
def api_health():
    """Alias de /health bajo el prefijo /api."""
    return jsonify({"status": "ok", "estado": "ok"}), 200


@health_bp.route("/quien")
def quien():
    """Identifica el contenedor/pod que respondio.

    Sirve para demostrar el balanceo entre replicas y el rolling update
    (la version cambia de 1.0 a 1.1 mientras el servicio sigue arriba).
    """
    return jsonify(
        {
            # En Docker/K8s el hostname es el ID del contenedor o el nombre
            # del pod.
            "pod": socket.gethostname(),
            "version": os.getenv("APP_VERSION", Config.APP_VERSION),
        }
    ), 200
