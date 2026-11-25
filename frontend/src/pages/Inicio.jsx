import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import api from '../services/api.js'
import Icono from '../components/Icono.jsx'
import { useAuth, INICIO_POR_ROL } from '../context/AuthContext.jsx'

// Frente D - Busqueda de viajes
import BuscarViajes from './cliente/BuscarViajes.jsx'

const BENEFICIOS = [
  { icono: 'asiento', titulo: 'Elige tu asiento', texto: 'Mira el mapa del bus y escoge ventana, pasillo o el piso que prefieras.' },
  { icono: 'qr', titulo: 'Boleto en tu celular', texto: 'Recibe tu boleto con código QR y preséntalo al subir al bus.' },
  { icono: 'dinero', titulo: 'Descuentos de ley', texto: 'Tercera edad, personas con discapacidad, niños y estudiantes pagan menos.' },
  { icono: 'escudo', titulo: 'Compra segura', texto: 'Solo cooperativas registradas y pagos validados por su personal.' },
]

const PASOS = [
  { titulo: 'Busca', texto: 'Origen, destino y fecha de tu viaje.' },
  { titulo: 'Elige', texto: 'El horario, la cooperativa y tus asientos.' },
  { titulo: 'Paga', texto: 'Con tarjeta o transferencia bancaria.' },
  { titulo: 'Viaja', texto: 'Muestra tu código QR al abordar.' },
]

// Página principal (rediseño CC-19)
function Inicio() {
  const { usuario, cargando } = useAuth()
  const [cooperativas, setCooperativas] = useState([])

  useEffect(() => {
    api.get('/cooperativas')
      .then(({ data }) => setCooperativas((Array.isArray(data) ? data : []).filter((c) => c.activa !== false)))
      .catch(() => {})
  }, [])

  // GC-9: el personal (admin y cooperativas) no compra pasajes: va a su propio inicio
  if (cargando) return <div className="cargando"><span className="giro" /> Cargando…</div>
  if (usuario && usuario.rol !== 'cliente') return <Navigate to={INICIO_POR_ROL[usuario.rol] || '/'} replace />

  return (
    <>
      <section className="portada">
        <div className="portada__interior">
          <span className="portada__etiqueta"><Icono nombre="ruta" tam={16} /> Viaja por todo el Ecuador</span>
          <h1>Tus pasajes de bus, <em>sin filas</em> y en minutos.</h1>
          <p>Compara horarios de las cooperativas, elige tu asiento y lleva tu boleto en el celular.</p>
        </div>
      </section>

      <div className="portada__buscador">
        {/* Frente D - Buscador de pasajes */}
        <BuscarViajes enInicio />
      </div>

      <section className="beneficios">
        <div className="rejilla-4">
          {BENEFICIOS.map((b) => (
            <article key={b.titulo} className="beneficio">
              <span className="beneficio__icono"><Icono nombre={b.icono} tam={24} /></span>
              <h3>{b.titulo}</h3>
              <p>{b.texto}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="beneficios" style={{ paddingTop: 0 }}>
        <span className="etiqueta-seccion">Así de fácil</span>
        <h2 style={{ marginBottom: '1.25rem' }}>Compra tu pasaje en 4 pasos</h2>
        <div className="pasos">
          {PASOS.map((p) => (
            <div key={p.titulo} className="paso">
              <strong>{p.titulo}</strong>
              <span>{p.texto}</span>
            </div>
          ))}
        </div>
      </section>

      {cooperativas.length > 0 && (
        <section className="beneficios" style={{ paddingTop: 0 }}>
          <div className="fila fila--entre" style={{ marginBottom: '1.25rem' }}>
            <div>
              <span className="etiqueta-seccion">Cooperativas</span>
              <h2 style={{ margin: 0 }}>Viaja con quienes conocen la ruta</h2>
            </div>
            <Link to="/viajes" className="btn">Ver todos los viajes <Icono nombre="flecha" tam={18} /></Link>
          </div>
          <div className="rejilla-3">
            {cooperativas.map((c) => (
              <article key={c.id} className="beneficio fila" style={{ flexWrap: 'nowrap' }}>
                {c.logo_url
                  ? <img src={c.logo_url} alt="" style={{ width: 52, height: 52, objectFit: 'contain', borderRadius: 12, border: '1px solid var(--borde)', padding: 4 }} />
                  : <span className="beneficio__icono" style={{ margin: 0, background: c.color_primario ? `${c.color_primario}1a` : undefined, color: c.color_primario || undefined }}><Icono nombre="bus" tam={24} /></span>}
                <div>
                  <h3 style={{ margin: 0 }}>{c.nombre}</h3>
                  <p>{c.eslogan || 'Transporte interprovincial de pasajeros'}</p>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </>
  )
}

export default Inicio
