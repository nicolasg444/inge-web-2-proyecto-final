# app/__init__.py

from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.routes.auth_routes import auth_bp
from app.routes.health import health_bp
from app.routes.main_routes import main_bp
from app.routes.project_routes import projects_bp
from app.routes.task_routes import tasks_bp
from app.routes.user_routes import users_bp

# Cabeceras de seguridad de la API. La API solo devuelve JSON, asi que la
# CSP mas estricta posible ("no cargar nada") no rompe nada y neutraliza
# cualquier HTML que alguien lograra colar en una respuesta.
# Las cabeceras de la pagina web (HTML) las pone Nginx: ver
# frontend/security-headers.conf.
CABECERAS_SEGURIDAD = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # Los navegadores ignoran HSTS sobre HTTP; cobra efecto cuando hay TLS
    # delante (Front Door / Ingress en produccion).
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # Respuestas con datos de usuario no deben quedar en caches intermedias.
    "Cache-Control": "no-store",
}


def aplicar_cabeceras_seguridad(respuesta):
    """Funcion centralizada: agrega las cabeceras a TODA respuesta."""
    for nombre, valor in CABECERAS_SEGURIDAD.items():
        respuesta.headers.setdefault(nombre, valor)
    return respuesta


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    # Antes era CORS(app) sin restricciones: cualquier sitio podia llamar
    # a la API desde el navegador. Ahora solo los origenes configurados.
    CORS(app, origins=Config.CORS_ORIGINS)

    app.after_request(aplicar_cabeceras_seguridad)

    app.register_blueprint(main_bp)

    app.register_blueprint(health_bp)

    app.register_blueprint(
        auth_bp,
        url_prefix="/api/auth"
    )

    app.register_blueprint(
        users_bp,
        url_prefix="/api/usuarios"
    )

    app.register_blueprint(
        projects_bp,
        url_prefix="/api/proyectos"
    )

    app.register_blueprint(
        tasks_bp,
        url_prefix="/api/tareas"
    )

    return app
