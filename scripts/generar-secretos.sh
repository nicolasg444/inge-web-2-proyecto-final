#!/usr/bin/env bash
# Genera los secretos aleatorios en secrets/ (ignorado por Git).
# - NO sobrescribe archivos existentes: regenerar la contrasena de MySQL con
#   el volumen ya inicializado dejaria a la API sin acceso.
# - Nunca imprime los valores.
# Uso: scripts/generar-secretos.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$RAIZ/secrets"

command -v openssl >/dev/null || { echo "Falta openssl" >&2; exit 1; }

# 700: otros usuarios del anfitrion no pueden ni listar la carpeta.
mkdir -p "$DIR"
chmod 700 "$DIR" 2>/dev/null || true

generar() { # $1=archivo $2=bytes aleatorios
  local archivo="$DIR/$1"
  if [ -s "$archivo" ]; then
    echo "  = $1 ya existe (no se toca)"
    return
  fi
  # Hexadecimal: sin caracteres especiales que rompan URLs, shells o YAML.
  # printf sin salto de linea final.
  printf '%s' "$(openssl rand -hex "$2")" > "$archivo"
  # 644 y no 600: los secretos de Compose (sin Swarm) son bind mounts que
  # conservan el dueno del anfitrion; los procesos del contenedor (UID
  # 10001, 999...) necesitan permiso de lectura. La carpeta 700 sigue
  # impidiendo el acceso a otros usuarios del anfitrion.
  chmod 644 "$archivo" 2>/dev/null || true
  echo "  + $1 generado"
}

echo "Secretos en $DIR:"
generar jwt_secret.txt 32           # 64 caracteres (>= 32 exigidos)
generar db_password.txt 24
generar mysql_root_password.txt 24
generar redis_password.txt 24
echo "Listo. Estos archivos NO se versionan (ver .gitignore)."
