#!/usr/bin/env node
// scripts/smoke-jwt.mjs - prueba de humo de seguridad contra un despliegue.
// Node 22+, sin dependencias (fetch y crypto nativos).
//
// Uso:
//   BASE_URL=http://localhost:8080 node scripts/smoke-jwt.mjs
//
// Credenciales (opcional): SMOKE_EMAIL / SMOKE_PASSWORD como variables o en
// el archivo .smoke.env de la raiz (ignorado por Git). Si no hay, se crea un
// usuario desechable que se borra al final.
// Prueba de token expirado: necesita el JWT_SECRET para firmar un token
// valido pero vencido; lo lee de SMOKE_JWT_SECRET_FILE o, si existe, de
// secrets/jwt_secret.txt. El valor nunca se imprime.
//
// Nunca se imprimen tokens, contrasenas ni secretos.

import { createHmac, randomBytes } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), '..')

// --- .smoke.env (formato CLAVE=valor) --------------------------------------
const archivoEnv = join(RAIZ, '.smoke.env')
if (existsSync(archivoEnv)) {
  for (const linea of readFileSync(archivoEnv, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$/)
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2]
  }
}

const BASE = (process.env.BASE_URL || 'http://localhost:8080').replace(/\/$/, '')

let fallos = 0
let omitidas = 0
const ok = (msg) => console.log(`  ✔ ${msg}`)
const mal = (msg) => { fallos++; console.log(`  ✘ ${msg}`) }
const omitir = (msg) => { omitidas++; console.log(`  - OMITIDA: ${msg}`) }
const verificar = (cond, msg, detalle = '') => (cond ? ok(msg) : mal(`${msg} ${detalle}`))
const titulo = (t) => console.log(`\n${t}`)

async function llamar(metodo, ruta, { token, cuerpo } = {}) {
  const headers = {}
  if (cuerpo !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  const r = await fetch(BASE + ruta, {
    method: metodo,
    headers,
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  })
  let datos = null
  const texto = await r.text()
  try { datos = JSON.parse(texto) } catch { datos = texto }
  return { status: r.status, headers: r.headers, datos }
}

// --- utilidades JWT ---------------------------------------------------------
const b64url = (x) => Buffer.from(typeof x === 'string' ? x : JSON.stringify(x)).toString('base64url')
function firmarHS256(payload, secreto) {
  const base = `${b64url({ alg: 'HS256', typ: 'JWT' })}.${b64url(payload)}`
  return `${base}.${createHmac('sha256', secreto).update(base).digest('base64url')}`
}
function leerSecretoJwt() {
  const ruta = process.env.SMOKE_JWT_SECRET_FILE || join(RAIZ, 'secrets', 'jwt_secret.txt')
  return existsSync(ruta) ? readFileSync(ruta, 'utf8').trim() : null
}

const creados = []
let token = null
let miId = null
let usuarioDesechable = false

try {
  console.log(`Smoke test de seguridad contra ${BASE}`)

  titulo('1. Endpoints publicos')
  const salud = await llamar('GET', '/health')
  verificar(salud.status === 200 && salud.datos?.estado === 'ok', 'GET /health -> 200 {"estado":"ok"}')
  const pods = new Set()
  for (let i = 0; i < 12; i++) {
    const q = await llamar('GET', '/quien')
    if (q.status === 200) pods.add(`${q.datos.pod} (v${q.datos.version})`)
  }
  verificar(pods.size >= 1, `GET /quien responde; pods distintos en 12 llamadas: ${pods.size}`)
  console.log(`    ${[...pods].join(', ')}`)

  titulo('2. Sin credenciales')
  const sin = await llamar('POST', '/api/proyectos', { cuerpo: { nombre: 'x' } })
  verificar(sin.status === 401, 'POST /api/proyectos sin token -> 401', `(fue ${sin.status})`)
  const sinGet = await llamar('GET', '/api/proyectos')
  verificar(sinGet.status === 401, 'GET /api/proyectos sin token -> 401', `(fue ${sinGet.status})`)

  titulo('3. Flujo completo: registro -> login -> escritura con JWT')
  let email = process.env.SMOKE_EMAIL
  let password = process.env.SMOKE_PASSWORD
  if (!email || !password) {
    usuarioDesechable = true
    email = `smoke-${randomBytes(4).toString('hex')}@ejemplo.test`
    password = randomBytes(18).toString('base64url')
  }
  let login = await llamar('POST', '/api/auth/login', { cuerpo: { email, password } })
  if (login.status === 401) {
    // Se intenta ademas registrarse como admin: el servidor debe ignorarlo.
    const reg = await llamar('POST', '/api/auth/register', {
      cuerpo: { nombre: 'Smoke Test', email, password, rol: 'admin' },
    })
    verificar(reg.status === 201, 'POST /api/auth/register -> 201', `(fue ${reg.status})`)
    verificar(reg.datos?.rol === 'usuario', 'el registro ignora "rol": admin enviado por el cliente')
    login = await llamar('POST', '/api/auth/login', { cuerpo: { email, password } })
  }
  verificar(login.status === 200 && typeof login.datos?.token === 'string', 'POST /api/auth/login -> 200 con token')
  token = login.datos?.token
  miId = login.datos?.usuario?.id
  if (!token) throw new Error('Sin token no se pueden ejecutar las demas pruebas')

  const crear = await llamar('POST', '/api/proyectos', { token, cuerpo: { nombre: 'Proyecto smoke', descripcion: 'prueba' } })
  verificar(crear.status === 201, 'POST /api/proyectos con Authorization -> 201', `(fue ${crear.status})`)
  if (crear.datos?.id) creados.push(crear.datos.id)

  titulo('4. Autorizacion (identidad tomada del JWT, no del cuerpo)')
  const rol = await llamar('PUT', `/api/usuarios/${miId}`, { token, cuerpo: { rol: 'admin' } })
  verificar(rol.status === 403, 'un usuario no puede subirse a admin -> 403', `(fue ${rol.status})`)
  const otro = await llamar('DELETE', `/api/usuarios/${Number(miId) + 1000000}`, { token })
  verificar(otro.status === 403, 'un usuario no puede borrar a otro -> 403', `(fue ${otro.status})`)
  omitir('CSRF: la API autentica con "Authorization: Bearer" (no cookies); ver DECISIONES.md')

  titulo('5. JWT manipulados')
  const [cab, cuerpo, firma] = token.split('.')
  const firmaAlterada = `${cab}.${cuerpo}.${firma[0] === 'A' ? 'B' : 'A'}${firma.slice(1)}`
  let r = await llamar('GET', '/api/proyectos', { token: firmaAlterada })
  verificar(r.status === 401, 'firma alterada -> 401', `(fue ${r.status})`)
  const payload = JSON.parse(Buffer.from(cuerpo, 'base64url').toString())
  r = await llamar('GET', '/api/proyectos', { token: `${cab}.${b64url({ ...payload, rol: 'admin' })}.${firma}` })
  verificar(r.status === 401, 'payload alterado (rol admin) con firma original -> 401', `(fue ${r.status})`)
  r = await llamar('GET', '/api/proyectos', { token: `${b64url({ alg: 'none', typ: 'JWT' })}.${b64url(payload)}.` })
  verificar(r.status === 401, 'alg "none" -> 401', `(fue ${r.status})`)
  r = await llamar('GET', '/api/proyectos', { token: 'esto.no.es-un-jwt' })
  verificar(r.status === 401, 'token mal formado -> 401', `(fue ${r.status})`)

  titulo('6. JWT expirado')
  const secreto = leerSecretoJwt()
  if (!secreto) {
    omitir('no hay secrets/jwt_secret.txt ni SMOKE_JWT_SECRET_FILE')
  } else {
    const ahora = Math.floor(Date.now() / 1000)
    const vencido = firmarHS256({ ...payload, iat: ahora - 7200, exp: ahora - 3600 }, secreto)
    r = await llamar('GET', '/api/proyectos', { token: vencido })
    verificar(r.status === 401 && r.datos?.error === 'Token expirado', 'token bien firmado pero vencido -> 401 "Token expirado"', `(fue ${r.status})`)
  }

  titulo('7. XSS almacenado se devuelve como texto')
  const xss = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
  const cx = await llamar('POST', '/api/proyectos', { token, cuerpo: { nombre: xss, descripcion: xss } })
  if (cx.datos?.id) creados.push(cx.datos.id)
  const lx = await llamar('GET', `/api/proyectos/${cx.datos?.id}`, { token })
  verificar(lx.datos?.nombre === xss, 'el payload se guarda y devuelve literal (sin interpretar)')
  verificar((lx.headers.get('content-type') || '').startsWith('application/json'), 'Content-Type: application/json (no text/html)')
  verificar(lx.headers.get('x-content-type-options') === 'nosniff', 'X-Content-Type-Options: nosniff en la respuesta')

  titulo('8. Cabeceras de seguridad (HTML via Nginx y API via Flask)')
  for (const [nombre, ruta] of [['HTML /', '/'], ['API /api/proyectos', '/api/proyectos'], ['API /health', '/health']]) {
    const h = (await fetch(BASE + ruta, { headers: token && ruta.startsWith('/api') ? { Authorization: `Bearer ${token}` } : {} })).headers
    const csp = h.get('content-security-policy') || ''
    verificar(csp.includes("frame-ancestors 'none'"), `${nombre}: Content-Security-Policy`)
    verificar(h.get('x-content-type-options') === 'nosniff', `${nombre}: X-Content-Type-Options`)
    // fetch une cabeceras repetidas con ", ": si aparece, esta duplicada.
    verificar(h.get('x-frame-options') === 'DENY', `${nombre}: X-Frame-Options (sin duplicar)`, `(fue "${h.get('x-frame-options')}")`)
    verificar(!csp.includes(', default-src'), `${nombre}: una sola CSP`)
    verificar(!/\d/.test(h.get('server') || ''), `${nombre}: Server sin version`)
  }

  titulo('9. Cache Redis (informativo)')
  const c1 = await llamar('GET', '/api/proyectos', { token })
  const c2 = await llamar('GET', '/api/proyectos', { token })
  const x1 = c1.headers.get('x-cache')
  const x2 = c2.headers.get('x-cache')
  if (x2 === 'HIT') {
    ok(`listado: ${x1} -> ${x2} (segunda lectura desde Redis)`)
    const cInv = await llamar('POST', '/api/proyectos', { token, cuerpo: { nombre: 'invalida cache' } })
    if (cInv.datos?.id) creados.push(cInv.datos.id)
    const c3 = await llamar('GET', '/api/proyectos', { token })
    verificar(c3.headers.get('x-cache') === 'MISS', 'una escritura invalida la cache (siguiente lectura MISS)')
    verificar(c3.datos.some?.((p) => p.id === cInv.datos?.id), 'el listado incluye el proyecto recien creado')
  } else {
    omitir(`cache no activa o sin Redis (X-Cache: ${x1} -> ${x2})`)
  }
} catch (error) {
  mal(`error inesperado: ${error.message}`)
} finally {
  titulo('10. Limpieza')
  for (const id of creados) {
    const d = await llamar('DELETE', `/api/proyectos/${id}`, { token }).catch(() => ({ status: 0 }))
    verificar(d.status === 200, `DELETE /api/proyectos/${id}`)
  }
  if (usuarioDesechable && token && miId) {
    const d = await llamar('DELETE', `/api/usuarios/${miId}`, { token }).catch(() => ({ status: 0 }))
    verificar(d.status === 200, 'borra el usuario desechable')
  }
  console.log(`\nResultado: ${fallos === 0 ? 'TODO EN VERDE' : `${fallos} FALLO(S)`}${omitidas ? ` (${omitidas} omitida(s))` : ''}`)
  process.exitCode = fallos === 0 ? 0 : 1
}
