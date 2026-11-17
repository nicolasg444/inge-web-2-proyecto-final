# Gestión de Proyectos y Tareas — Ingeniería Web II

API REST en **Flask** (JWT) con base de datos **MySQL**, caché **Redis** y
frontend **React (Vite)** servido por **Nginx**. Se ejecuta en contenedores
con **Docker Compose** y en **Kubernetes** (kind). El diseño en Azure está en
[docs/arquitectura-azure.md](docs/arquitectura-azure.md) y la justificación
de cada decisión en [DECISIONES.md](DECISIONES.md).

```
navegador ──► web (Nginx :8080) ──► api (Gunicorn :8000) ──► mysql (:3306)
               React estático         Flask + JWT          └► redis (:6379, caché)
```

## Requisitos

| Herramienta | Versión | Para |
|---|---|---|
| Docker Engine / Docker Desktop | 24+ | todo |
| Docker Compose | v2+ (`docker compose`) | entorno Compose |
| kubectl | 1.30+ | Kubernetes |
| kind | 0.23+ | clúster local |
| Node.js | 22+ | `scripts/smoke-jwt.mjs` |
| bash + openssl | Linux, WSL o Git Bash | scripts |

## Inicio rápido con Docker Compose (desde un clon limpio)

```bash
git clone <url-del-repo> && cd Ingenieria_Web_II
bash scripts/generar-secretos.sh                 # crea secrets/*.txt (no se versionan)
docker compose -f compose.yaml up -d --build --wait
BASE_URL=http://localhost:8080 node scripts/smoke-jwt.mjs
```

- Web: <http://localhost:8080>. Salud: `/health`. Réplica que responde: `/quien`. API: `/api/...`
- Si el **8080 está ocupado** (Apache/XAMPP, por ejemplo), usa otro puerto:
  `WEB_PORT=8085 docker compose -f compose.yaml up -d --build --wait`, o
  agrega `WEB_PORT=8085` a `.env`.
- `docker compose -f compose.yaml ps` debe mostrar `mysql`, `redis`, `api` y
  `web` en `(healthy)`, y `api-init` en `Exited (0)` (creó las tablas).
- No hay API keys que pegar a mano: los cuatro secretos (JWT, MySQL app,
  MySQL root y Redis) son aleatorios y los genera el script.

### Modo desarrollo

`docker compose up -d --build`, sin `-f`, aplica además
[compose.override.yaml](compose.override.yaml). Ese archivo monta `app/`
desde tu equipo, recarga Gunicorn al guardar y expone la API directa en
`127.0.0.1:8000`.

### Sin contenedores (como antes)

```bash
cp .env.example .env          # o ajusta tu .env existente (ver abajo)
pip install -r requirements-dev.txt
python init_db.py && python run.py          # API en http://127.0.0.1:5000
cd frontend && npm install && npm run dev   # React en http://localhost:5173
python -m pytest                            # pruebas (no necesitan MySQL)
```

> **Si ya tenías un `.env`**: la app ahora **no arranca** sin `JWT_SECRET`
> y rechaza el antiguo valor de ejemplo de `SECRET_KEY`. Agrega
> `JWT_SECRET_FILE=secrets/jwt_secret.txt` (después de correr
> `scripts/generar-secretos.sh`) y borra `SECRET_KEY`. `DB_PASSWORD` puede
> quedarse en `.env` para tu MySQL local, o moverse a un archivo con
> `DB_PASSWORD_FILE`.

## Kubernetes (kind)

```bash
bash scripts/k8s-up.sh                     # clúster + imágenes + Secret + kubectl apply -f k8s/
BASE_URL=http://localhost:8081 node scripts/smoke-jwt.mjs
```

`k8s-up.sh` crea el clúster `ingweb` (1 control-plane + 2 workers). Luego
construye `ingweb-api:1.0`, `ingweb-api:1.1` e `ingweb-web:1.0`, las carga en
los nodos, crea el Secret desde `secrets/` y aplica los manifiestos. Desde
cero tarda unos 3 minutos. La web queda en <http://localhost:8081>; el
puerto es distinto del de Compose para poder tener ambos levantados.

Todos los comandos usan `--context kind-ingweb`, así nunca tocan otro
clúster que tengas como contexto actual:

```bash
K="kubectl --context kind-ingweb -n ingweb"
$K get pods -o wide                                        # 3 api repartidas entre workers

# Balanceo: 12 peticiones desde un pod del clúster
$K exec deploy/web -- sh -c 'for i in $(seq 12); do wget -qO- http://api:8000/quien; echo; done'

# Autorreparación: borrar un pod y ver cómo se recrea
POD=$($K get pods -l app.kubernetes.io/name=api -o jsonpath='{.items[0].metadata.name}')
$K delete pod "$POD" --wait=false
$K get pods -l app.kubernetes.io/name=api -w              # Ctrl+C para salir

# Rolling update 1.0 -> 1.1 con vigía (cuenta líneas FALLO), y rollback
bash scripts/k8s-rolling.sh 1.1
bash scripts/k8s-rolling.sh undo

# Drain de un worker respetando el PDB (minAvailable 2)
kubectl --context kind-ingweb drain ingweb-worker2 --ignore-daemonsets --delete-emptydir-data
kubectl --context kind-ingweb uncordon ingweb-worker2

# Clase QoS de cada pod
$K get pods -o custom-columns='POD:.metadata.name,QOS:.status.qosClass'
```

Laboratorio de recursos (OOMKilled y Pending):
[k8s/laboratorio/README.md](k8s/laboratorio/README.md). HPA opcional:
[k8s/extras/hpa-api.yaml](k8s/extras/hpa-api.yaml) (requiere
metrics-server).

> Antes de drenar, revisa en qué worker está `mysql-0`
> (`$K get pod mysql-0 -o wide`) y drena **el otro**. Su volumen local está
> atado a ese nodo: si drenas ese worker, MySQL queda `Pending` hasta el
> `uncordon`.

## Prueba de humo de seguridad

```bash
BASE_URL=http://localhost:8080 node scripts/smoke-jwt.mjs
```

Comprueba lo siguiente:

- endpoints públicos;
- 401 sin token;
- registro, login y escritura con JWT, y que el `rol` enviado por el cliente
  se ignora;
- 403 al intentar subirse a admin o borrar a otro usuario;
- 401 con firma alterada, payload alterado, `alg: none`, token mal formado y
  token expirado (este último usa `secrets/jwt_secret.txt` y nunca imprime su
  valor);
- XSS almacenado devuelto como texto JSON con `nosniff`;
- cabeceras de seguridad en HTML y en la API, sin duplicados;
- caché HIT/MISS y su invalidación;
- limpieza de los datos de prueba.

Por defecto crea un usuario desechable y lo borra al terminar. Para usar uno
fijo, crea `.smoke.env` (ignorado por Git) con `SMOKE_EMAIL=...` y
`SMOKE_PASSWORD=...`.

## Medición y evidencia

```bash
bash scripts/medir-imagenes.sh   # tabla: imagen ingenua vs optimizada
bash scripts/evidencia.sh        # guarda todo en docs/evidencia/ (sin secretos)
```

[Dockerfile.ingenuo](Dockerfile.ingenuo) es **material de laboratorio**:
contiene errores a propósito y un secreto falso, para comparar.

Lo que `evidencia.sh` **no** puede capturar y hay que hacer a mano
(captura de pantalla o grabación):

1. **Rolling update en vivo**: dos terminales. En una,
   `bash scripts/vigia.sh http://localhost:8081/quien 0.2`. En la otra,
   `kubectl --context kind-ingweb -n ingweb set image deploy/api api=ingweb-api:1.1 init-db=ingweb-api:1.1`.
   Captura cómo la versión pasa de 1.0 a 1.1 y el `RESUMEN: ... FALLO=0`
   al pulsar Ctrl+C.
2. **Drain**: la salida con `Cannot evict pod as it would violate the pod's disruption budget`
   junto al vigía sin fallos.
3. **La app en el navegador** (<http://localhost:8080>), con DevTools →
   Network mostrando las cabeceras CSP y X-Frame-Options.
4. **Diagrama de Azure** como imagen: pega el bloque Mermaid de
   `docs/arquitectura-azure.md` en <https://mermaid.live> y exporta PNG.

## Limpieza

| Comando | Qué borra | Qué conserva |
|---|---|---|
| `docker compose -f compose.yaml down` | contenedores y redes | volúmenes `mysql-data` y `redis-data` (usuarios, proyectos, tareas) |
| `docker compose -f compose.yaml down -v` | lo anterior **y los volúmenes**: **se pierden todos los datos de MySQL** | imágenes |
| `bash scripts/k8s-down.sh` | el clúster kind entero, incluido el volumen de MySQL | imágenes locales, `secrets/` |

`secrets/` no se borra con nada de lo anterior. Si lo borras con un volumen
de MySQL ya inicializado, la API pierde el acceso: la contraseña nueva no
coincide con la guardada. En ese caso haz `down -v` y empieza de cero.

## Estructura

```
app/                  API Flask (config.py: secretos; cache.py: Redis)
tests/                pruebas pytest (sin MySQL ni Redis)
frontend/             React + Dockerfile + nginx/ (cabeceras y proxy)
Dockerfile            imagen de la API (multi-etapa: deps, test, runtime)
Dockerfile.ingenuo    laboratorio: la versión "mala" para comparar
compose.yaml          entorno completo; compose.override.yaml = desarrollo
k8s/                  manifiestos (kubectl apply -f k8s/)
  kind/               configuración del clúster (no se aplica con kubectl)
  laboratorio/        OOMKilled / Pending (se aplican a mano)
  extras/             HPA opcional
scripts/              secretos, k8s-up/down, smoke, medición, evidencia, vigía
docs/                 OpenAPI, arquitectura Azure, evidencia
```
