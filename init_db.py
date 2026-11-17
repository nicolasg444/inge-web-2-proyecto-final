# init_db.py
# Crea la base de datos y las tablas si no existen (idempotente):
#   python init_db.py
#
# En Docker Compose lo ejecuta el servicio "api-init" y en Kubernetes un
# initContainer, antes de arrancar la API. Reintenta porque MySQL puede
# tardar en aceptar conexiones la primera vez que inicializa su volumen.

import os
import sys
import time

import mysql.connector

from app.repositories.db import init_db

if __name__ == "__main__":
    intentos = int(os.getenv("INIT_DB_REINTENTOS", "30"))
    for intento in range(1, intentos + 1):
        try:
            init_db()
            print("Base de datos y tablas creadas correctamente.")
            sys.exit(0)
        except mysql.connector.Error as error:
            # Solo el codigo de error: el mensaje podria incluir el usuario.
            print(
                f"MySQL no disponible (errno {error.errno}), "
                f"intento {intento}/{intentos}...",
                flush=True,
            )
            time.sleep(2)
    print("No se pudo inicializar la base de datos.", file=sys.stderr)
    sys.exit(1)
