// src/api.js
// Capa de acceso al backend Flask. La URL se toma de la variable
// de entorno VITE_API_URL definida en el archivo .env
//
// - Desarrollo (npm run dev): VITE_API_URL=http://127.0.0.1:5000
// - Contenedor (Nginx): VITE_API_URL vacia -> rutas relativas al mismo
//   origen; Nginx reenvia /api, /health y /quien a la API. Se usa "??" y no
//   "||" para que la cadena vacia sea un valor valido.

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:5000'

// Realiza una peticion generica al backend y devuelve el JSON.
async function request(ruta, opciones = {}) {
  const respuesta = await fetch(`${API_URL}${ruta}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opciones,
  })

  if (!respuesta.ok) {
    throw new Error(`Error ${respuesta.status} al consultar ${ruta}`)
  }

  return respuesta.json()
}

// GET /health -> { status: "ok" }
export function getHealth() {
  return request('/health')
}

// GET /quien -> { pod, version } (contenedor que respondio)
export function getQuien() {
  return request('/quien')
}

// GET / -> informacion general de la API (solo en desarrollo: detras de
// Nginx, "/" es la pagina React)
export function getInfo() {
  return request('/')
}

export { API_URL }
