# syntax=docker/dockerfile:1

# Imagen web: build de React (Vite) servido por Nginx sin privilegios.
#   docker build -t ingweb-web:1.0 frontend/

# Versiones FIJAS. Node solo existe en la etapa de build: no llega a la
# imagen final (que no necesita Node para servir archivos estaticos).
ARG NODE_VERSION=22.21.1
ARG NGINX_VERSION=1.30.0

# ---------------------------------------------------------------------------
# Etapa 1: build -> genera dist/ (HTML, JS y CSS minificados)
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine3.22 AS build
WORKDIR /src

# Primero manifiesto y lockfile: npm ci solo se repite si cambian las
# dependencias. npm ci respeta el lockfile exacto (build reproducible).
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY index.html vite.config.js ./
COPY public/ public/
COPY src/ src/

# Vacia = mismo origen: el navegador llama /api, /health y /quien al mismo
# Nginx que sirve la pagina. Asi no hay CORS ni URLs fijas en el bundle.
# OJO: todo VITE_* queda PUBLICO dentro del JS; jamas poner secretos aqui.
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------------------------------------------------------------------------
# Etapa 2: runtime -> solo Nginx + archivos estaticos
# ---------------------------------------------------------------------------
# nginx-unprivileged corre como usuario nginx (UID 101) y escucha en 8080;
# la imagen oficial "nginx" arranca como root para abrir el puerto 80.
FROM nginxinc/nginx-unprivileged:${NGINX_VERSION}-alpine AS runtime

# Configuracion propia (archivos propiedad de root, solo lectura para nginx).
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf nginx/proxy-api.conf /etc/nginx/snippets/

# Solo el resultado del build: ni node_modules ni el codigo fuente.
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 8080

# wget viene en BusyBox (Alpine). /salud-web no depende de la API.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/salud-web"]
