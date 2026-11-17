#!/usr/bin/env bash
# Levanta todo en Kubernetes (kind) desde cero, en orden:
#   1. cluster kind  2. imagenes  3. carga en kind  4. namespace
#   5. Secret desde secrets/  6. kubectl apply -f k8s/  7. espera rollout
# Idempotente: se puede ejecutar varias veces.
# Uso: scripts/k8s-up.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"
export MSYS_NO_PATHCONV=1   # Git Bash: no convertir rutas tipo /run/...

CLUSTER=ingweb
# --context explicito: nunca tocar otro cluster que este como actual.
K="kubectl --context kind-$CLUSTER"
NS=ingweb
IMAGENES_TERCEROS=(mysql:8.4.7 redis:7.4.6-alpine)

paso() { printf '\n==> %s\n' "$*"; }

paso "1/7 Cluster kind '$CLUSTER'"
if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo "ya existe"
else
  kind create cluster --config k8s/kind/kind-ingweb.yaml
fi

paso "2/7 Secretos locales"
[ -s secrets/jwt_secret.txt ] || bash scripts/generar-secretos.sh

paso "3/7 Construyendo imagenes"
docker build -q --build-arg APP_VERSION=1.0 -t ingweb-api:1.0 .
# Misma base de codigo; solo cambia la version que reporta /quien. Sirve
# para demostrar el rolling update 1.0 -> 1.1 y el rollback.
docker build -q --build-arg APP_VERSION=1.1 -t ingweb-api:1.1 .
docker build -q -t ingweb-web:1.0 frontend/

paso "4/7 Cargando imagenes en los nodos de kind"
# Las imagenes propias no estan en ningun registro: hay que copiarlas a
# cada nodo (por eso imagePullPolicy: IfNotPresent en los manifiestos).
kind load docker-image --name "$CLUSTER" ingweb-api:1.0 ingweb-api:1.1 ingweb-web:1.0
for img in "${IMAGENES_TERCEROS[@]}"; do
  docker image inspect "$img" >/dev/null 2>&1 || docker pull -q "$img"
  # Si falla (p. ej. imagen multi-arquitectura con el almacen containerd de
  # Docker Desktop), los nodos la descargan solos de Docker Hub.
  kind load docker-image --name "$CLUSTER" "$img" >/dev/null 2>&1 \
    || echo "aviso: no se pudo precargar $img; los nodos la descargaran"
done

paso "5/7 Namespace y Secret"
$K apply -f k8s/00-namespace.yaml
# El Secret NO esta en k8s/ (seria subir credenciales a Git). Se crea desde
# los archivos de secrets/. "--dry-run=client -o yaml | apply" lo hace
# idempotente (crea o actualiza). Ningun valor se imprime.
$K -n "$NS" create secret generic ingweb-secretos \
  --from-file=jwt_secret=secrets/jwt_secret.txt \
  --from-file=db_password=secrets/db_password.txt \
  --from-file=mysql_root_password=secrets/mysql_root_password.txt \
  --from-file=redis_password=secrets/redis_password.txt \
  --dry-run=client -o yaml | $K apply -f - >/dev/null
echo "secret/ingweb-secretos aplicado"

paso "6/7 kubectl apply -f k8s/"
$K apply -f k8s/

paso "7/7 Esperando a que todo este listo"
$K -n "$NS" rollout status statefulset/mysql --timeout=300s
$K -n "$NS" rollout status deployment/redis --timeout=120s
$K -n "$NS" rollout status deployment/api --timeout=300s
$K -n "$NS" rollout status deployment/web --timeout=120s

$K -n "$NS" get pods -o wide
cat <<FIN

Listo:  http://localhost:8081   (/health, /quien, /api/...)
Prueba: BASE_URL=http://localhost:8081 node scripts/smoke-jwt.mjs
Bajar:  scripts/k8s-down.sh
FIN
