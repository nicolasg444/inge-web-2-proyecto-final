// src/api.js
// Capa de acceso al backend Flask. La URL se toma de la variable
// de entorno VITE_API_URL definida en el archivo .env

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000'

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

// GET / -> informacion general de la API
export function getInfo() {
  return request('/')
}

export { API_URL }
