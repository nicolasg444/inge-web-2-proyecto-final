# app/cache.py
"""Cache de lecturas en Redis con degradacion elegante.

- Se cachean los listados GET /api/proyectos y GET /api/tareas (TTL corto,
  CACHE_TTL segundos, 30 por defecto) para reducir consultas a MySQL.
- Los listados son GLOBALES (todo usuario autenticado ve todos los
  proyectos), por eso la clave es por recurso y no por usuario: una clave
  por usuario no protegeria nada y dejaria a los demas viendo datos viejos
  despues de una escritura.
- Cada POST/PUT/DELETE invalida las claves afectadas.
- Si Redis no responde, la API sigue funcionando contra MySQL: se registra
  una advertencia (sin datos sensibles) y se deja de intentar durante
  _PAUSA_TRAS_FALLO segundos para no sumar latencia a cada peticion.
  La cache NUNCA provoca un 500.
"""

import logging
import socket
import threading
import time

import redis
from flask import current_app

from app.config import Config

log = logging.getLogger(__name__)

_PREFIJO = "cache:"
_PAUSA_TRAS_FALLO = 10

_cliente = None
_pausa_hasta = 0.0


def _resolver(host, limite=0.5):
    """Resuelve el nombre con limite de tiempo.

    socket_connect_timeout no cubre la resolucion DNS: con el contenedor de
    Redis detenido, getaddrinfo("redis") puede tardar varios segundos en una
    red "internal" de Docker. Se resuelve en un hilo y se abandona a tiempo.
    """
    resultado = {}

    def tarea():
        try:
            resultado["ip"] = socket.getaddrinfo(
                host, None, socket.AF_INET, socket.SOCK_STREAM
            )[0][4][0]
        except OSError as error:
            resultado["error"] = error

    hilo = threading.Thread(target=tarea, daemon=True)
    hilo.start()
    hilo.join(limite)
    if "ip" not in resultado:
        raise redis.ConnectionError("resolucion DNS fallida o lenta")
    return resultado["ip"]


def _obtener_cliente():
    """Cliente perezoso; None si la cache esta desactivada o en pausa."""
    global _cliente
    if not Config.REDIS_HOST or time.monotonic() < _pausa_hasta:
        return None
    if _cliente is None:
        try:
            ip = _resolver(Config.REDIS_HOST)
        except redis.ConnectionError as error:
            _registrar_fallo("conexion", error)
            return None
        # Se conecta a la IP resuelta; si Redis cambia de IP (contenedor o
        # pod recreado) la conexion falla, el cliente se descarta y en el
        # siguiente intento se vuelve a resolver el nombre.
        _cliente = redis.Redis(
            host=ip,
            port=Config.REDIS_PORT,
            password=Config.REDIS_PASSWORD,
            # Timeouts cortos: una cache lenta es peor que no tener cache.
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
            decode_responses=True,
        )
    return _cliente


def _registrar_fallo(operacion, error):
    global _pausa_hasta, _cliente
    _pausa_hasta = time.monotonic() + _PAUSA_TRAS_FALLO
    # Descarta el cliente para volver a resolver el nombre al reintentar.
    _cliente = None
    # Solo el tipo de error: el mensaje podria incluir host/credenciales.
    log.warning(
        "Redis no disponible en %s (%s); se usa MySQL directamente",
        operacion,
        type(error).__name__,
    )


def leer(recurso):
    cliente = _obtener_cliente()
    if cliente is None:
        return None
    try:
        return cliente.get(_PREFIJO + recurso)
    except redis.RedisError as error:
        _registrar_fallo("lectura", error)
        return None


def guardar(recurso, cuerpo_json):
    cliente = _obtener_cliente()
    if cliente is None:
        return
    try:
        cliente.set(_PREFIJO + recurso, cuerpo_json, ex=Config.CACHE_TTL)
    except redis.RedisError as error:
        _registrar_fallo("escritura", error)


def invalidar(*recursos):
    cliente = _obtener_cliente()
    if cliente is None:
        return
    try:
        cliente.delete(*(_PREFIJO + r for r in recursos))
    except redis.RedisError as error:
        # Si la invalidacion falla, el dato viejo expira solo en CACHE_TTL.
        _registrar_fallo("invalidacion", error)


def listado_cacheado(recurso, consultar):
    """Devuelve una respuesta JSON del listado, desde Redis o desde MySQL.

    Se guarda el JSON ya serializado por Flask para que una respuesta de
    cache sea identica byte a byte a una de MySQL (fechas incluidas).
    La cabecera X-Cache (HIT/MISS) permite verlo en la demostracion.
    """
    cuerpo = leer(recurso)
    estado = "HIT"
    if cuerpo is None:
        cuerpo = current_app.json.dumps(consultar())
        guardar(recurso, cuerpo)
        estado = "MISS"
    respuesta = current_app.response_class(
        cuerpo, status=200, mimetype="application/json"
    )
    respuesta.headers["X-Cache"] = estado
    return respuesta
