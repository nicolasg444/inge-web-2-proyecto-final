# app/config.py

import os

from dotenv import load_dotenv

load_dotenv()


class Config:

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "cambia-esta-clave-secreta-en-produccion"
    )

    JWT_EXP_HOURS = int(os.getenv("JWT_EXP_HOURS", "8"))

    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "ingenieria_web")

    SWAGGER = {
        "title": "API Ingenieria Web II",
        "uiversion": 3,
    }
