# app/repositories/task_repository.py

from app.repositories.db import get_connection


def create(titulo, descripcion, estado, proyecto_id, asignado_a):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tareas "
        "(titulo, descripcion, estado, proyecto_id, asignado_a) "
        "VALUES (%s, %s, %s, %s, %s)",
        (titulo, descripcion, estado, proyecto_id, asignado_a),
    )
    conn.commit()
    new_id = cur.lastrowid
    cur.close()
    conn.close()
    return new_id


def get_all():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM tareas")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_by_id(task_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM tareas WHERE id = %s", (task_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def update(task_id, titulo, descripcion, estado, asignado_a):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tareas SET titulo = %s, descripcion = %s, "
        "estado = %s, asignado_a = %s WHERE id = %s",
        (titulo, descripcion, estado, asignado_a, task_id),
    )
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    return affected


def delete(task_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tareas WHERE id = %s", (task_id,))
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    return affected
