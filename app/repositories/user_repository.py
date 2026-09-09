# app/repositories/user_repository.py

from app.repositories.db import get_connection


def _dict_cursor(conn):
    return conn.cursor(dictionary=True)


def create(nombre, email, password, rol="usuario"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (nombre, email, password, rol) "
        "VALUES (%s, %s, %s, %s)",
        (nombre, email, password, rol),
    )
    conn.commit()
    new_id = cur.lastrowid
    cur.close()
    conn.close()
    return new_id


def get_all():
    conn = get_connection()
    cur = _dict_cursor(conn)
    cur.execute(
        "SELECT id, nombre, email, rol, creado_en FROM usuarios"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_by_id(user_id):
    conn = get_connection()
    cur = _dict_cursor(conn)
    cur.execute(
        "SELECT id, nombre, email, rol, creado_en "
        "FROM usuarios WHERE id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def get_by_email(email):
    conn = get_connection()
    cur = _dict_cursor(conn)
    cur.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def update(user_id, nombre, email, rol):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET nombre = %s, email = %s, rol = %s "
        "WHERE id = %s",
        (nombre, email, rol, user_id),
    )
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    return affected


def delete(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    return affected
