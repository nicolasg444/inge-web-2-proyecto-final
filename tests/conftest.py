# tests/conftest.py
# Las pruebas no necesitan MySQL ni Redis: configuran secretos de prueba
# ANTES de importar la app (Config lee los secretos al importarse).
import os
import secrets

import pytest

os.environ["JWT_SECRET"] = secrets.token_hex(32)
os.environ.pop("JWT_SECRET_FILE", None)
os.environ["DB_PASSWORD"] = "solo-pruebas"
os.environ.pop("DB_PASSWORD_FILE", None)
os.environ.pop("REDIS_HOST", None)
os.environ["CORS_ORIGINS"] = "http://localhost:5173"


@pytest.fixture
def app():
    from app import create_app

    aplicacion = create_app()
    aplicacion.config["TESTING"] = True
    return aplicacion


@pytest.fixture
def client(app):
    return app.test_client()
