# app/repositories/project_repository.py

from app.repositories.db import get_connection


def create(nombre, descripcion, propietario_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO proyectos (nombre, descripcion, propietario_id) "
        "VALUES (%s, %s, %s)",
        (nombre, descripcion, propietario_id),
    )
    conn.commit()
    new_id = cur.lastrowid
    cur.close()
    conn.close()
    return new_id


def get_all():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM proyectos")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_by_id(project_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM proyectos WHERE id = %s", (project_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def update(project_id, nombre, descripcion):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE proyectos SET nombre = %s, descripcion = %s WHERE id = %s",
        (nombre, descripcion, project_id),
    )
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    return affected


def delete(project_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM proyectos WHERE id = %s", (project_id,))
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    return affected
