# Imagen ingenua vs optimizada
# Generado: 2026-11-17 00:20:29

>> Construccion inicial (calienta la cache)...
>> Reconstruccion tras modificar un archivo de app/...

| Metrica | Ingenua (`ingweb-api:ingenua`) | Optimizada (`ingweb-api:1.0`) |
|---|---|---|
| Tamano en disco | 1.83GB | 349MB |
| Capas (docker history) | 17 | 20 |
| Usuario (whoami) | root | app |
| Reconstruccion tras tocar app/ | 32.1 s | 2.8 s |
| Secreto en docker history --no-trunc | SI (visible) | NO |

Nota: el secreto de la imagen ingenua es FALSO (secreto-de-ejemplo-NO-USAR).
