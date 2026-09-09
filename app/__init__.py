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


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    CORS(app)

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