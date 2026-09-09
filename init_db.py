# init_db.py
# Ejecutar una sola vez para crear la base de datos y las tablas:
#   python init_db.py

from app.repositories.db import init_db

if __name__ == "__main__":
    init_db()
    print("Base de datos y tablas creadas correctamente.")
