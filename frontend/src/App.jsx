import { useEffect, useState } from 'react'
import { getHealth, getQuien, API_URL } from './api'
import './App.css'

function App() {
  const [estado, setEstado] = useState(null)
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [quien, setQuien] = useState(null)

  // Consulta el endpoint /health del backend Flask
  const consultar = () => {
    setCargando(true)
    setError(null)

    getHealth()
      .then((datos) => setEstado(datos.status))
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false))

    // Contenedor/pod que respondio (demuestra el balanceo entre replicas)
    getQuien()
      .then(setQuien)
      .catch(() => setQuien(null))
  }

  useEffect(() => {
    consultar()
  }, [])

  let indicador
  if (cargando) {
    indicador = <span className="badge badge--cargando">Consultando...</span>
  } else if (error) {
    indicador = <span className="badge badge--error">Sin conexion</span>
  } else {
    indicador = <span className="badge badge--ok">{estado}</span>
  }

  return (
    <main className="app">
      <header className="app__header">
        <h1>Gestion de Proyectos y Tareas</h1>
        <p className="app__sub">Ingenieria Web II &middot; Frontend React + Backend Flask</p>
      </header>

      <section className="tarjeta">
        <h2>Estado del backend</h2>

        <div className="tarjeta__fila">
          <span className="etiqueta">GET /health</span>
          {indicador}
        </div>

        <div className="tarjeta__fila">
          <span className="etiqueta">API</span>
          <code className="url">{API_URL || window.location.origin}</code>
        </div>

        {quien && (
          <div className="tarjeta__fila">
            <span className="etiqueta">GET /quien</span>
            <code className="url">{quien.pod} &middot; v{quien.version}</code>
          </div>
        )}

        {error && <p className="mensaje-error">{error}</p>}

        <button className="boton" onClick={consultar} disabled={cargando}>
          {cargando ? 'Consultando...' : 'Volver a consultar'}
        </button>
      </section>

      <footer className="app__pie">
        React (localhost:5173) &rarr; HTTP &rarr; Flask (localhost:5000)
      </footer>
    </main>
  )
}

export default App
