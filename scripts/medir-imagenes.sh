#!/usr/bin/env bash
# Compara la imagen ingenua (Dockerfile.ingenuo) con la optimizada
# (Dockerfile) e imprime una tabla Markdown lista para el informe.
# Uso: scripts/medir-imagenes.sh            (desde cualquier carpeta)
# Compatible con Linux, WSL y Git Bash.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

# Git Bash convierte rutas como /app en C:/Program Files/Git/app; se desactiva.
export MSYS_NO_PATHCONV=1

ING="ingweb-api:ingenua"
OPT="ingweb-api:1.0"
CAMBIO="app/_medicion_tmp.txt"

# Si el script se interrumpe, no dejar el archivo temporal en el repo.
trap 'rm -f "$CAMBIO"' EXIT

ahora_ms() {
  # %N (nanosegundos) existe en GNU date (Linux, WSL, Git Bash).
  echo $(( $(date +%s%N) / 1000000 ))
}

construir() { # $1=dockerfile $2=tag
  docker build -q -f "$1" -t "$2" . >/dev/null
}

echo ">> Construccion inicial (calienta la cache)..." >&2
construir Dockerfile.ingenuo "$ING"
construir Dockerfile "$OPT"

echo ">> Reconstruccion tras modificar un archivo de app/..." >&2
medir_rebuild() { # $1=dockerfile $2=tag
  echo "cambio $(date +%s%N)" > "$CAMBIO"
  local t0; t0=$(ahora_ms)
  construir "$1" "$2"
  echo "$(( ($(ahora_ms) - t0) ))"
}
T_ING=$(medir_rebuild Dockerfile.ingenuo "$ING")
T_OPT=$(medir_rebuild Dockerfile "$OPT")
rm -f "$CAMBIO"
# Reconstruir sin el archivo temporal para que la imagen final quede limpia.
construir Dockerfile "$OPT"
construir Dockerfile.ingenuo "$ING"

tamano()  { docker image ls "$1" --format '{{.Size}}' | head -1; }
capas()   { docker history -q "$1" | wc -l | tr -d ' '; }
usuario() { docker run --rm --entrypoint whoami "$1" 2>/dev/null || echo "?"; }
secreto_en_historia() {
  # Solo se informa SI/NO; nunca se imprime el valor encontrado.
  if docker history --no-trunc "$1" | grep -qiE "secret|password|token"; then
    echo "SI (visible)"
  else
    echo "NO"
  fi
}
segundos() { awk -v ms="$1" 'BEGIN { printf "%.1f s", ms/1000 }'; }

echo
echo "| Metrica | Ingenua (\`$ING\`) | Optimizada (\`$OPT\`) |"
echo "|---|---|---|"
echo "| Tamano en disco | $(tamano "$ING") | $(tamano "$OPT") |"
echo "| Capas (docker history) | $(capas "$ING") | $(capas "$OPT") |"
echo "| Usuario (whoami) | $(usuario "$ING") | $(usuario "$OPT") |"
echo "| Reconstruccion tras tocar app/ | $(segundos "$T_ING") | $(segundos "$T_OPT") |"
echo "| Secreto en docker history --no-trunc | $(secreto_en_historia "$ING") | $(secreto_en_historia "$OPT") |"
echo
echo "Nota: el secreto de la imagen ingenua es FALSO (secreto-de-ejemplo-NO-USAR)."
