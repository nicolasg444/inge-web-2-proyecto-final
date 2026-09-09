# app/repositories/db.py

import mysql.connector

from app.config import Config


def get_connection(use_database=True):
    """Devuelve una conexion nueva a MySQL."""

    params = {
        "host": Config.DB_HOST,
        "port": Config.DB_PORT,
        "user": Config.DB_USER,
        "password": Config.DB_PASSWORD,
    }

    if use_database:
        params["database"] = Config.DB_NAME

    return mysql.connector.connect(**params)


def init_db():
    """Crea la base de datos y las tablas si no existen."""

    conn = get_connection(use_database=False)
    cur = conn.cursor()

    cur.execute(
        f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cur.execute(f"USE {Config.DB_NAME}")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(120) NOT NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            rol VARCHAR(50) NOT NULL DEFAULT 'usuario',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS proyectos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(150) NOT NULL,
            descripcion TEXT,
            propietario_id INT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (propietario_id)
                REFERENCES usuarios(id) ON DELETE SET NULL
        ) ENGINE=InnoDB
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tareas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            titulo VARCHAR(150) NOT NULL,
            descripcion TEXT,
            estado VARCHAR(50) NOT NULL DEFAULT 'pendiente',
            proyecto_id INT,
            asignado_a INT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proyecto_id)
                REFERENCES proyectos(id) ON DELETE CASCADE,
            FOREIGN KEY (asignado_a)
                REFERENCES usuarios(id) ON DELETE SET NULL
        ) ENGINE=InnoDB
        """
    )

    conn.commit()
    cur.close()
    conn.close()
