# gunicorn.conf.py
# Configuracion del servidor WSGI de produccion (contenedores).
#
# Apagado ordenado: al recibir SIGTERM (lo que envian "docker stop" y
# Kubernetes), Gunicorn deja de aceptar conexiones, espera a que las
# peticiones en curso terminen (hasta graceful_timeout) y sale con codigo 0.
# Eso es lo que permite rolling updates sin errores.

import os

# 0.0.0.0: dentro del contenedor hay que escuchar en todas las interfaces;
# 127.0.0.1 solo seria accesible desde el propio contenedor.
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8000')}"

# Procesos trabajadores. Pocos y fijos: en K8s se escala con replicas, no con
# workers, y cada worker consume memoria del limite del contenedor.
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))

# Menor que terminationGracePeriodSeconds (30 s) menos el preStop (5 s):
# Gunicorn debe terminar antes de que Kubernetes envie SIGKILL.
graceful_timeout = 20
timeout = 30

# El latido de los workers se escribe aqui. /tmp es tmpfs/emptyDir porque el
# sistema de archivos raiz es de solo lectura.
worker_tmp_dir = "/tmp"

# Logs a stdout/stderr: el runtime (Docker/K8s) los recoge. El formato de
# acceso por defecto NO incluye cabeceras (ni Authorization ni cookies).
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Necesario detras de Nginx para registrar la IP real del cliente.
forwarded_allow_ips = "*"
