# Decisiones técnicas

Cada decisión responde tres preguntas: **qué hace**, **por qué** y **qué se
descartó**. Sirve para estudiar y para justificar cada línea en la
socialización. Los archivos tienen además comentarios en las líneas no
obvias.

---

## 1. Imágenes Docker

### 1.1 Imagen base con versión fija: `python:3.13.9-slim-trixie`, `node:22.21.1-alpine3.22`, `nginxinc/nginx-unprivileged:1.30.0-alpine`
- **Qué**: cada `FROM` nombra una versión exacta.
- **Por qué**: `:latest` cambia sin aviso. El mismo Dockerfile produciría
  otra imagen mañana, con otro Python u otras vulnerabilidades, y un error no
  se podría reproducir.
- **Descartado**: `python:latest` (es lo que usa el Dockerfile ingenuo).
  También `python:3.13-alpine`: Python sobre musl obliga a compilar paquetes
  que no traen *wheels* para Alpine, y el resultado no es más pequeño.

### 1.2 Multi-etapa: `deps` → `test` → `runtime`
- **Qué**: `deps` instala las dependencias en un venv; `test` agrega pytest y
  ejecuta las pruebas; `runtime` copia **solo** el venv sin pip y el código.
- **Por qué**: pytest, pip y la caché de instalación no llegan a producción.
  Si una prueba falla, `docker build --target test` falla.
- **Descartado**: una sola etapa (todo queda en la imagen) o instalar con
  `--user` (rutas menos predecibles).
- **Resultado** (ver `docs/evidencia/03-medicion.md`): 1,83 GB → 349 MB.

### 1.3 Orden de capas: primero `requirements.txt`, después el código
- **Qué**: `COPY requirements.txt` + `pip install` van antes de `COPY app/`.
- **Por qué**: Docker reutiliza una capa si nada de lo que hay antes cambió.
  Editar código no invalida la capa de dependencias. Reconstruir pasa de
  ~35 s (ingenuo) a ~3 s.
- **Descartado**: `COPY . .` al principio. Cualquier cambio reinstala todo.

### 1.4 Usuario sin privilegios (UID/GID 10001) y código propiedad de root
- **Qué**: `useradd --uid 10001`, `USER app`. Los archivos se copian **sin**
  `--chown`.
- **Por qué**: si alguien explota la app, no es root y no puede modificar el
  código que se ejecuta ni instalar nada. Un UID fijo y alto evita chocar con
  usuarios del sistema y permite exigirlo en Kubernetes (`runAsUser: 10001`).
- **Descartado**: correr como root (lo que hace la imagen por defecto) o dar
  al usuario la propiedad del código.

### 1.5 Gunicorn y `CMD` en forma exec
- **Qué**: `CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]`.
- **Por qué**: el servidor de Werkzeug (`app.run`) es para desarrollo, y con
  `debug=True` permite ejecutar código remoto. Con la forma exec, Gunicorn es
  el PID 1 y recibe SIGTERM: deja de aceptar conexiones, termina las
  peticiones en curso (`graceful_timeout = 20`) y sale con 0. Eso es lo que
  permite el rolling update sin errores.
- **Descartado**: `CMD python run.py` en forma shell. `/bin/sh` sería el PID
  1 y no reenvía la señal, y Docker mata el proceso a los 10 s.

### 1.6 HEALTHCHECK con Python (sin curl)
- **Qué**: `python -c "urllib.request.urlopen('http://127.0.0.1:8000/health')"`.
- **Por qué**: la imagen slim no trae curl, e instalarlo agrega peso y
  superficie de ataque. Python ya está.

### 1.7 `.dockerignore` estricto
- **Qué**: excluye `.git`, `.env*`, `secrets/`, `*.pem`, `node_modules/`,
  `frontend/`, `k8s/`, `docs/`.
- **Por qué**: todo lo que no se excluye viaja al *builder*, y con un `COPY`
  amplio terminaría en la imagen. El historial de Git podría contener
  secretos viejos.

### 1.8 Frontend: build en Node, se sirve con Nginx sin privilegios
- **Qué**: la etapa `build` (Node) genera `dist/`. La imagen final es
  `nginx-unprivileged` (UID 101, puerto 8080) con solo esos archivos.
- **Por qué**: servir estáticos no requiere Node. La imagen final (82 MB,
  medido) no trae Node, node_modules ni el código fuente. La imagen `nginx`
  oficial arranca como root para abrir el puerto 80.
- **`VITE_API_URL=""`**: mismo origen. El navegador llama `/api` al mismo
  Nginx: no hay CORS ni URLs fijas. En `api.js` se cambió `||` por `??` para
  que la cadena vacía sea válida.

---

## 2. Nginx

### 2.1 `proxy_pass http://api:8000;` **sin** barra final
- **Por qué**: con `http://api:8000/` Nginx reemplaza el prefijo de la
  `location`, y `/api/proyectos` llegaría a Flask como `/proyectos`, que da
  404. Las rutas de Flask incluyen `/api`.

### 2.2 Cabeceras de seguridad solo en las `location` de estáticos
- **Qué**: `security-headers.conf` se incluye en `/` y `/assets/`, no a nivel
  `server`.
- **Por qué**: si estuvieran a nivel `server`, Nginx las sumaría también a
  las respuestas de la API, que ya traen las suyas desde Flask. El navegador
  aplicaría **dos** CSP (la intersección) y X-Frame-Options quedaría
  `DENY, DENY`. Ojo: en Nginx, un `add_header` dentro de una `location`
  anula los heredados del `server`; por eso se usa `include` en cada una.
- **Dos CSP distintas a propósito**:
  - **HTML**: `default-src 'self'`. Carga solo JS y CSS propios; el build de
    Vite no necesita `'unsafe-inline'`.
  - **API**: `default-src 'none'`. Solo devuelve JSON, así que no debe cargar
    nada.
- `smoke-jwt.mjs` verifica que no haya cabeceras duplicadas.

### 2.3 Authorization, Cookie y Set-Cookie no se declaran
- **Por qué**: Nginx reenvía todas las cabeceras de la petición y de la
  respuesta por defecto. Escribir `proxy_set_header Authorization ""` las
  **borraría**.

### 2.4 `/salud-web` propio de Nginx
- **Por qué**: si la salud de la web dependiera de la API, una caída de la
  API reiniciaría también las réplicas web sin arreglar nada.

### 2.5 Sin fallback a `index.html`
- **Por qué**: la app no tiene enrutador del lado del cliente. Una ruta
  inexistente debe ser un 404 real.

### 2.6 Limitación conocida: DNS de `api` en Compose
- Nginx resuelve `api` al arrancar. Si en Compose se **recrea** solo el
  contenedor `api` (cambia su IP), haz `docker compose restart web`. En
  Kubernetes no pasa: el Service tiene una IP fija.

---

## 3. Docker Compose

### 3.1 Redes `frontend` y `backend` (`internal: true`)
- **Qué**:
  - `mysql` y `redis`: solo en `backend`.
  - `api`: en `backend` y `frontend`.
  - `web`: solo en `frontend`.
  - Solo `web` publica un puerto.
- **Por qué**: la web no puede ni resolver el nombre `redis` (comprobado:
  `NXDOMAIN`). Una red `internal` no tiene salida ni entrada externa: ni un
  puerto publicado por error sería alcanzable. La API necesita estar en
  `frontend` para que la web la alcance.
- **Descartado**: una sola red (todo ve todo) o publicar 3306/6379 al
  anfitrión.

### 3.2 Secretos de Compose y `*_FILE`
- **Qué**: los secretos son archivos montados en `/run/secrets/<nombre>`. La
  app lee `JWT_SECRET_FILE` con `leer_secreto()`, y MySQL lee
  `MYSQL_PASSWORD_FILE`.
- **Por qué**: una variable de entorno aparece en `docker inspect`, en
  `/proc/<pid>/environ`, en volcados de errores y en los logs de algunas
  herramientas. Un archivo no. Comprobado: `docker inspect` solo muestra las
  rutas.
- **Permisos 644 en una carpeta 700**: sin Swarm, los secretos son *bind
  mounts* que conservan el dueño del anfitrión. El proceso del contenedor
  (UID 10001, 999) necesita leerlos. La carpeta 700 impide el acceso a otros
  usuarios del anfitrión.
- **Descartado**: `environment: JWT_SECRET=...` o `env_file` con secretos.

### 3.3 Fallar rápido si falta un secreto
- **Qué**: `leer_secreto()` lanza un error si falta el secreto, si es muy
  corto (JWT_SECRET < 32) o si es el antiguo valor de ejemplo.
- **Por qué**: antes, `config.py` tenía `SECRET_KEY` por defecto con un
  valor **publicado en Git**. Cualquiera podía firmar un JWT de admin. Un
  secreto con valor por defecto es un secreto público.
- **Descartado**: valores por defecto "para que funcione en desarrollo".

### 3.4 `read_only: true` + `tmpfs: /tmp`, `cap_drop: ALL`, `no-new-privileges`
- **Qué**:
  - raíz del contenedor de solo lectura (comprobado con `touch`, que da
    `Read-only file system`);
  - sin *capabilities* de Linux;
  - sin escalar privilegios con binarios setuid.
- **Por qué**: si alguien explota la app, no puede dejar binarios, modificar
  código ni volverse root. Gunicorn solo escribe su latido en `/tmp` (RAM).
- **Excepción**: MySQL conserva sus capabilities en Compose porque su
  entrypoint cambia de root a `mysql`. En Kubernetes corre directamente como
  999 con `drop: ALL`.

### 3.5 Redis con `user: "999:1000"`
- **Por qué**: el entrypoint oficial solo baja de root a `redis` cuando el
  comando empieza por `redis-server`. Como aquí se usa `sh -c` para leer la
  contraseña del secreto, seguiría como root. Se fija el usuario desde el
  arranque.
- La contraseña se lee al arrancar (`$$(cat ...)`), así que no aparece en
  `docker inspect`. El healthcheck hace un `PING` **autenticado** con
  `REDISCLI_AUTH`, que evita pasar la clave como argumento.

### 3.6 `api-init` como tarea única y `depends_on` con condiciones
- **Qué**: `api-init` ejecuta `init_db.py` (idempotente) y termina. `api`
  espera `service_completed_successfully` de `api-init` y `service_healthy`
  de mysql y redis.
- **Por qué**: crear tablas es una tarea de una sola vez, no de cada
  réplica. La API no arranca contra una base sin tablas.
- **Descartado**: `depends_on` sin condición, que solo espera a que el
  contenedor *exista*, no a que esté listo.

### 3.7 Nombre y usuario de la base fijos en `compose.yaml`
- **Por qué**: el `.env` de desarrollo local suele tener `DB_USER=root`, y la
  imagen de MySQL no permite `MYSQL_USER=root`. Además no son secretos.

### 3.8 `compose.override.yaml` solo para desarrollo
- `docker compose up` lo aplica solo. Monta el código y recarga Gunicorn.
  Producción local: `docker compose -f compose.yaml up -d`.

---

## 4. Redis como caché

### 4.1 Qué se cachea y con qué clave
- **Qué**: `GET /api/proyectos` y `GET /api/tareas`, con TTL de 30 s
  (`CACHE_TTL`). La clave es **por recurso** (`cache:proyectos`). Cada
  POST/PUT/DELETE la invalida.
- **Por qué la clave no es por usuario**: en esta API los listados son
  **globales** (cualquier usuario autenticado ve todos los proyectos). Una
  clave por usuario no protegería nada y, tras una escritura, los demás
  usuarios verían datos viejos hasta 30 s. Si algún día los listados se
  filtran por usuario, la clave debe incluir el `sub` del JWT verificado.
- Se guarda el JSON **ya serializado por Flask**, así que una respuesta de
  caché es idéntica byte a byte a una de MySQL. La cabecera `X-Cache:
  HIT/MISS` permite demostrarlo.

### 4.2 Degradación elegante
- **Qué**: si Redis falla, se registra una advertencia (solo el tipo de
  error) y se lee de MySQL. Se deja de intentar durante 10 s para no sumar
  latencia a cada petición. La caché **nunca** provoca un 500.
- **Hallazgo**: con el contenedor de Redis detenido, `getaddrinfo("redis")`
  tardaba **4 a 8 s** en la red `internal`, y `socket_connect_timeout` no
  cubre el DNS. Se agregó una resolución con límite de 0,5 s. Medido: el
  peor caso pasó de 8 s a 0,5 s.

### 4.3 Por qué la librería `redis` (redis-py) y no el protocolo a mano
- RESP es simple, pero un cliente correcto necesita *pool* de conexiones,
  timeouts, reconexión, autenticación, TLS (para Azure Cache for Redis) y
  manejo de errores parciales. Es código de infraestructura que no aporta al
  curso y donde un error sería silencioso. redis-py es el cliente oficial.

### 4.4 Redis sin persistencia en Kubernetes
- **Por qué**: solo guarda copias con TTL de 30 s. Si se pierde, la API
  recalienta la caché desde MySQL, que es la fuente de verdad. En Compose se
  deja el volumen `redis-data` (requisito de la guía), pero no es necesario.

---

## 5. Seguridad de la aplicación

### 5.1 JWT
- **Qué**:
  - `algorithms=["HS256"]` (lista blanca): rechaza `none` y cualquier otro
    algoritmo;
  - `require: exp, iat, sub`;
  - PyJWT compara la firma con `hmac.compare_digest`, en tiempo constante.
- **Pruebas**: firma alterada, payload alterado, `alg: none`, HS512, token
  expirado y token sin `exp` dan 401 (pytest y smoke).
- **Sin estado**: cualquier réplica valida cualquier token porque todas
  tienen el mismo `JWT_SECRET` (mismo Secret). Comprobado en kind: el login
  en un pod y las peticiones atendidas por otros funcionan.

### 5.2 Escalada de privilegios corregida
- **Antes**: `POST /api/auth/register` aceptaba `"rol": "admin"` del
  cliente, y cualquier usuario autenticado podía cambiar el rol de cualquiera
  con `PUT /api/usuarios/<id>`.
- **Ahora**:
  - el registro siempre crea `usuario`;
  - solo un admin cambia roles;
  - un usuario solo edita o borra su propia cuenta;
  - la identidad sale del `sub` del JWT verificado, nunca del cuerpo.
- **Pendiente (decisión de dominio)**: proyectos y tareas siguen editables
  por cualquier usuario autenticado, y `propietario_id` se acepta del
  cliente. Si el modelo es "cada usuario sus proyectos", hay que filtrar por
  `propietario_id = sub`.
- **Efecto secundario**: el `rol` dentro del JWT es el del momento del
  login. Si un admin cambia el rol de alguien, el cambio aplica en su
  siguiente login (máximo `JWT_EXP_HOURS`).

### 5.3 CSRF: por qué no se implementó un token CSRF
- **CSRF** abusa de que el navegador **adjunta cookies solo** a peticiones
  hacia otro sitio. Esta API autentica con `Authorization: Bearer`, que el
  navegador **nunca** agrega solo. Una página maliciosa no puede enviarlo
  sin conocer el token, y no puede leerlo: está en el JS de nuestro origen.
- Agregar un token CSRF que se entrega junto al JWT en la misma respuesta no
  agregaría protección, solo complejidad. Se deja una prueba "OMITIDA" en el
  smoke que lo documenta.
- **Si se migra el JWT a una cookie** (p. ej. `HttpOnly` contra XSS), CSRF
  pasa a ser obligatorio: `SameSite=Lax/Strict` más un token *double-submit*
  ligado al JWT y comparado en tiempo constante.

### 5.4 CORS restringido
- **Antes** era `CORS(app)` (cualquier origen). **Ahora** solo
  `CORS_ORIGINS` (por defecto el Vite de desarrollo). Detrás de Nginx todo es
  mismo origen y CORS no interviene.

### 5.5 XSS
- React escapa todo lo que muestra. La API devuelve `application/json` con
  `nosniff` y CSP `default-src 'none'`, así que aunque alguien guarde
  `<script>`, el navegador nunca lo interpreta como HTML. El smoke lo
  verifica.

### 5.6 `/health` sin dependencias externas
- No consulta MySQL ni Redis. Si lo hiciera, una caída de MySQL haría que la
  *liveness* reiniciara las 3 réplicas en bucle sin arreglar nada.

---

## 6. Kubernetes

### 6.1 Orden de los archivos y subcarpetas
- `kubectl apply -f k8s/` aplica en orden alfabético y **no** es recursivo.
  - `00-namespace` va primero.
  - `01-limitrange` va antes que los pods, porque solo afecta a pods creados
    después.
  - `kind/`, `laboratorio/` y `extras/` no se aplican.

### 6.2 Pod Security Admission `restricted` en el namespace
- **Qué**: el API server **rechaza** cualquier pod que no sea no-root, sin
  escalada de privilegios, `drop: ALL` y seccomp `RuntimeDefault`.
  Comprobado: `kubectl run intruso` da `Forbidden`.
- **Por qué**: convierte el mínimo privilegio en una regla que se verifica,
  no en una costumbre.

### 6.3 `securityContext` de la API
- `runAsNonRoot`, `runAsUser: 10001`, `allowPrivilegeEscalation: false`,
  `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`,
  `seccompProfile: RuntimeDefault`.
- `fsGroup: 10001` y `defaultMode: 0440` hacen que los secretos montados
  solo los lea el grupo de la app.

### 6.4 Secretos: creados por script, montados como archivos
- El Secret **no** está en `k8s/`; subirlo sería publicar credenciales. Lo
  crea `k8s-up.sh` desde `secrets/` con `create secret --dry-run=client -o
  yaml | apply`, que es idempotente.
- Cada pod monta **solo** las claves que usa (`items:`). La API no ve la
  contraseña root de MySQL.
- Advertencia: un Secret de Kubernetes es base64, **no** cifrado. En Azure
  se reemplaza por Key Vault con el CSI Secrets Store Driver.

### 6.5 `automountServiceAccountToken: false`
- **Hallazgo**: Kubernetes monta el token de la ServiceAccount en
  `/var/run/secrets/kubernetes.io/...`, y `/var/run` es un enlace a `/run`.
  Al montar nuestro Secret de solo lectura en `/run/secrets`, el contenedor
  **no arrancaba** ("read-only file system").
- **Por qué es correcto de todos modos**: ninguna de estas apps habla con la
  API de Kubernetes, y un token montado es una credencial que un atacante
  podría robar.

### 6.6 `enableServiceLinks: false`
- **Hallazgo**: por cada Service, Kubernetes inyecta variables estilo Docker
  links. El Service `redis` generaba `REDIS_PORT=tcp://10.96.x.x:6379`, que
  pisaba nuestra configuración (`int()` fallaba). Los Services se encuentran
  por DNS.

### 6.7 MySQL como StatefulSet con 1 réplica
- **Por qué**: identidad estable (`mysql-0`) y un PVC propio que sobrevive a
  la recreación del pod. Una sola réplica porque varias réplicas sobre
  volúmenes distintos serían bases distintas; replicar MySQL requiere un
  operador. En Azure se usa Azure Database for MySQL.
- **Limitación observada**: si el pod de un StatefulSet queda roto, actualizar
  el manifiesto **no** lo reemplaza solo. Hay que borrar el pod
  (`kubectl delete pod mysql-0`). Es una limitación conocida de los
  StatefulSets: con un pod que nunca llega a Ready, el controlador no
  avanza la actualización.
- **Volumen local**: en kind el PV está atado a un nodo. Si se drena ese
  nodo, MySQL queda Pending hasta el `uncordon`.

### 6.8 initContainer `init-db`
- Crea las tablas antes de cada pod de la API. Es idempotente (`IF NOT
  EXISTS`) y reintenta mientras MySQL no responda. Así el despliegue desde
  cero no necesita orden manual: comprobado, sin reinicios.
- **Descartado**: un Job aparte, que obligaría a esperar a que termine antes
  de aplicar la API.

### 6.9 Probes
| Probe | Para qué | Si falla |
|---|---|---|
| `startupProbe` (60 s de margen) | da tiempo a arrancar sin que la liveness lo mate | sigue esperando; después reinicia |
| `readinessProbe` | decide si el pod recibe tráfico | lo **saca del Service**, sin reiniciar |
| `livenessProbe` | detecta un proceso colgado | **reinicia** el contenedor |

Las tres usan `/health`, que no depende de servicios externos (ver 5.6).

### 6.10 Rolling update sin caídas
- **Qué**:
  - `maxUnavailable: 0` y `maxSurge: 1`: nunca baja de 3 pods listos y crea
    de a uno;
  - `preStop: sleep 5`;
  - `terminationGracePeriodSeconds: 30`, que debe ser mayor que el preStop
    (5 s) más `graceful_timeout` (20 s).
- **Por qué el preStop**: al borrar un pod, Kubernetes envía SIGTERM y **en
  paralelo** lo quita de los Endpoints. Sin la espera, Gunicorn cierra antes
  de que kube-proxy deje de enviarle tráfico.
- **Medido**: 1.0 → 1.1 dio 64 OK y 0 FALLO; el `rollout undo` dio 62 OK y 0
  FALLO.
- **`APP_VERSION` no está en el manifiesto**: viene del `ENV` de la imagen.
  Si se fijara en el Deployment, `set image ... 1.1` seguiría reportando 1.0.

### 6.11 PodDisruptionBudget `minAvailable: 2`
- **Medido**: durante `kubectl drain`, Kubernetes respondió `Cannot evict pod
  as it would violate the pod's disruption budget`, esperó a que el
  reemplazo estuviera listo y luego siguió. Hubo 0 fallos.
- Solo protege de interrupciones **voluntarias** (drain, actualizaciones de
  nodos). Contra la caída de un nodo protegen las réplicas repartidas.
- Al hacer `uncordon` los pods **no vuelven solos** a ese nodo: Kubernetes no
  rebalancea. Lo harán en el siguiente rollout.

### 6.12 `topologySpreadConstraints` por `kubernetes.io/hostname`
- `maxSkew: 1` y `ScheduleAnyway`: reparte las 3 réplicas entre los 2
  workers (2+1). Es una preferencia: con un solo nodo, igual programa.
- `matchLabelKeys: [pod-template-hash]` calcula el reparto por versión
  (ReplicaSet), así los pods viejos no distorsionan el reparto de los nuevos
  durante un rollout.
- En Azure se usaría `topology.kubernetes.io/zone` (zonas de
  disponibilidad).

### 6.13 requests/limits y QoS
- **API**: requests `100m/128Mi`, limits `500m/256Mi`.
- **Requests**: lo que el scheduler **reserva**. Si no cabe, el pod queda
  Pending (laboratorio `api-gigante`).
- **Limits**: el techo. La CPU por encima se frena; la memoria por encima se
  mata (laboratorio `glotona`: `OOMKilled`, exit 137).
- **QoS Burstable** (comprobado) porque requests ≠ limits. Puede usar CPU
  libre del nodo, pero ante presión de memoria se desaloja antes que un
  Guaranteed.
- **Para Guaranteed**: requests **igual** a limits en CPU y memoria, en
  **todos** los contenedores del pod, initContainers incluidos (p. ej.
  `500m/256Mi` en ambos). Es más predecible, pero reserva más recursos.

### 6.14 LimitRange sin `max`
- Da valores por defecto a pods sin `resources` (p. ej. uno de depuración).
- No fija `max` a propósito: con `max`, el laboratorio `api-gigante` sería
  **rechazado** al crearlo en lugar de quedar **Pending**, que es lo que hay
  que mostrar.

### 6.15 `imagePullPolicy: IfNotPresent` y etiquetas fijas
- En kind las imágenes se cargan con `kind load` y no existen en ningún
  registro: con `Always` fallaría la descarga.
- Las etiquetas `1.0` y `1.1` son inmutables. Con `:latest`, Kubernetes
  usaría `Always` por defecto y no se sabría qué versión corre.

### 6.16 Services
- **`api` (ClusterIP)**: el mismo nombre que en Compose, así Nginx usa la
  misma configuración. `targetPort: http`, por nombre.
- **`mysql` (headless)**: lo exige el StatefulSet; el DNS apunta directo al
  pod.
- **`web` (NodePort 30080)**: kind lo publica en `127.0.0.1:8081`. Es 8081 y
  no 8080 para poder tener Compose y kind a la vez, y porque en el equipo de
  desarrollo el 8080 estaba ocupado. En producción sería un `LoadBalancer`
  interno o un Ingress detrás de Front Door.

### 6.17 Clúster kind de 3 nodos
- Con 1 control-plane y 2 workers se puede mostrar el reparto entre nodos y
  el drain. Requiere ~8 GB para Docker; con menos, deja un solo worker (se
  pierde esa demostración).

---

## 7. Repositorio

### 7.1 `.gitattributes` con LF
- Con `core.autocrlf=true` (Windows), los `.sh` saldrían con CRLF en un clon
  de Windows. Al ejecutarlos en WSL o Linux, bash falla con
  `$'\r': command not found`.

### 7.2 Estructura: no se movieron archivos
- La guía sugería carpetas `api/` y `web/`. Aquí la API sigue en la raíz
  (Dockerfile en la raíz) y el frontend en `frontend/` (con su Dockerfile).
  Mover todo rompería las rutas que el equipo ya usa sin aportar nada a los
  contenedores. Cada imagen tiene su propio contexto y `.dockerignore`.

### 7.3 `requirements.txt` y `requirements-dev.txt`
- pytest se movió a `requirements-dev.txt` para que no entre en la imagen.
  `gunicorn==23.0.0` y `redis==5.2.1` se agregaron con versión fija.
