# syntax=docker/dockerfile:1
# ^ Fija la sintaxis del Dockerfile (BuildKit). Habilita --mount=type=cache.

# Imagen de la API Flask (Gunicorn). Construccion:
#   docker build -t ingweb-api:1.0 .
#   docker build --target test .        <- ejecuta las pruebas

# Version FIJA (nunca :latest): el mismo Dockerfile debe producir la misma
# imagen hoy y en seis meses. "slim" (Debian) en lugar de "alpine" porque
# Python en Alpine (musl) obliga a compilar muchos paquetes sin wheels.
ARG PYTHON_VERSION=3.13.9

# ---------------------------------------------------------------------------
# Etapa 1: deps -> instala SOLO dependencias de produccion en un venv.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS deps

# No generar .pyc ni guardar cache de pip dentro de la capa.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Un venv en ruta fija se copia entero a la etapa final (sin pip ni
# herramientas de build en runtime).
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Primero SOLO requirements.txt: mientras no cambien las dependencias, esta
# capa sale de cache aunque cambie el codigo (reconstrucciones en segundos).
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia del venv sin pip para runtime: en produccion nadie instala paquetes,
# y una herramienta menos es superficie de ataque menos (y ~12 MB menos).
RUN cp -a /opt/venv /opt/venv-runtime \
 && /opt/venv-runtime/bin/python -m pip uninstall -y -q pip

# ---------------------------------------------------------------------------
# Etapa 2: test -> dependencias de desarrollo + pruebas. No llega a runtime.
# ---------------------------------------------------------------------------
FROM deps AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
WORKDIR /app
COPY app/ app/
COPY tests/ tests/
# Si una prueba falla, el build falla: no se publica una imagen rota.
RUN python -m pytest -q -p no:cacheprovider

# ---------------------------------------------------------------------------
# Etapa 3: runtime -> imagen final minima.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS runtime

# Version que reporta /quien. Se cambia en el build:
#   docker build --build-arg APP_VERSION=1.1 -t ingweb-api:1.1 .
ARG APP_VERSION=1.0

# PYTHONUNBUFFERED: los logs salen al instante (docker logs / kubectl logs).
# PYTHONDONTWRITEBYTECODE: el sistema de archivos es de solo lectura.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${APP_VERSION} \
    PORT=8000

# Usuario y grupo sin privilegios con UID/GID fijo (10001). Fijo para que
# Kubernetes pueda verificarlo (runAsUser: 10001) y para no chocar con
# usuarios del sistema (<1000). Sin shell de login ni home.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home \
    --shell /usr/sbin/nologin app

WORKDIR /app

# Solo el venv de produccion (sin pytest, sin pip cache).
COPY --from=deps /opt/venv-runtime /opt/venv

# El codigo queda propiedad de root (no se usa --chown): si alguien explota
# la app como usuario "app", no puede modificar el codigo que se ejecuta.
COPY gunicorn.conf.py run.py init_db.py ./
COPY app/ app/

# Puerto documental: quien publica el puerto es Compose/K8s.
EXPOSE 8000

# A partir de aqui todo corre como usuario sin privilegios.
USER app

# Healthcheck sin curl (no esta en slim): el propio Python consulta /health,
# que no depende de MySQL ni Redis. Kubernetes ignora HEALTHCHECK y usa sus
# probes; Docker/Compose si lo usan.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# Forma exec (JSON): Gunicorn es el PID 1 y recibe SIGTERM directamente, lo
# que permite el apagado ordenado. En forma shell, /bin/sh seria el PID 1 y
# no reenviaria la senal (el contenedor moriria por SIGKILL a los 10 s).
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]
