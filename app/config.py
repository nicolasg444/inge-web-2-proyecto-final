# app/config.py
"""Configuracion central de la aplicacion.

Reglas:
- Los SECRETOS se leen con leer_secreto(): primero NOMBRE_FILE (ruta a un
  archivo, p. ej. /run/secrets/jwt_secret, que es como Docker Compose y
  Kubernetes entregan los secretos) y si no existe, la variable NOMBRE.
  Si falta, la app NO arranca: fallar rapido es intencional; un secreto con
  valor por defecto es un secreto publico.
- La configuracion NO secreta tiene valores por defecto compatibles con el
  desarrollo local de siempre (python run.py).
- Nunca se imprime el valor de un secreto, ni siquiera en los errores.
"""

import os

from dotenv import load_dotenv

# Carga .env solo para desarrollo local. En contenedores no existe .env
# (lo excluye .dockerignore) y las variables llegan desde Compose/K8s.
load_dotenv()

# Valor de ejemplo que estuvo publicado en .env.example y en este archivo.
# Como es publico, cualquiera podria firmar JWT con el: se rechaza.
_SECRETOS_PUBLICOS = {"cambia-esta-clave-secreta-en-produccion"}


class ErrorConfiguracion(RuntimeError):
    """Error de configuracion que impide arrancar la aplicacion."""


def leer_secreto(nombre, min_largo=1):
    """Devuelve el secreto NOMBRE leyendo NOMBRE_FILE o, si no, NOMBRE.

    Lanza ErrorConfiguracion si no esta definido o es demasiado corto.
    Los mensajes de error nombran la variable, nunca el valor.
    """
    ruta = os.getenv(f"{nombre}_FILE")
    if ruta:
        try:
            with open(ruta, encoding="utf-8") as archivo:
                # strip() quita el salto de linea final que dejan los editores
                # y "echo"; un secreto con espacios al borde seria un error.
                valor = archivo.read().strip()
        except OSError as error:
            raise ErrorConfiguracion(
                f"No se pudo leer {nombre}_FILE ({error.strerror})"
            ) from None
    else:
        valor = os.getenv(nombre, "").strip()

    if not valor:
        raise ErrorConfiguracion(
            f"Falta el secreto {nombre}: define {nombre}_FILE "
            f"(ruta a un archivo) o {nombre}"
        )
    if len(valor) < min_largo:
        raise ErrorConfiguracion(
            f"El secreto {nombre} debe tener al menos {min_largo} caracteres"
        )
    if valor in _SECRETOS_PUBLICOS:
        raise ErrorConfiguracion(
            f"El secreto {nombre} usa un valor de ejemplo publico; "
            "genera uno nuevo (scripts/generar-secretos.sh)"
        )
    return valor


def _lista(valor):
    return [item.strip() for item in valor.split(",") if item.strip()]


class Config:

    # --- Secretos (obligatorios) -------------------------------------------
    # HS256 con una clave de menos de 32 bytes es atacable por fuerza bruta.
    JWT_SECRET = leer_secreto("JWT_SECRET", min_largo=32)
    DB_PASSWORD = leer_secreto("DB_PASSWORD")

    # --- Configuracion no secreta ------------------------------------------
    JWT_EXP_HOURS = int(os.getenv("JWT_EXP_HOURS", "8"))

    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_NAME = os.getenv("DB_NAME", "ingenieria_web")

    APP_VERSION = os.getenv("APP_VERSION", "1.0")

    # Origenes permitidos para CORS (solo hace falta en desarrollo, cuando
    # Vite corre en :5173 y Flask en :5000). Detras de Nginx todo es mismo
    # origen y CORS no interviene.
    CORS_ORIGINS = _lista(
        os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
    )

    # --- Cache Redis (opcional) --------------------------------------------
    # Sin REDIS_HOST la cache queda desactivada (desarrollo local simple).
    # Con REDIS_HOST la contrasena es obligatoria: Redis sin contrasena en
    # una red compartida es una puerta abierta.
    REDIS_HOST = os.getenv("REDIS_HOST", "")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD = leer_secreto("REDIS_PASSWORD") if REDIS_HOST else None
    CACHE_TTL = int(os.getenv("CACHE_TTL", "30"))

    SWAGGER = {
        "title": "API Ingenieria Web II",
        "uiversion": 3,
    }
