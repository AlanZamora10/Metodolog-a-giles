import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { mensajeDeError } from '../../services/api.js'
import { useAuth } from '../../context/AuthContext.jsx'
import Icono from '../../components/Icono.jsx'

/*
  GC-9: panel de inicio del personal de una cooperativa
  (usuario cooperativa, oficinista y personal del bus).
  Muestra el resumen del día de SU cooperativa y accesos rápidos según el rol.
*/

const NOMBRE_ROL = { cooperativa: 'Administración de la cooperativa', oficinista: 'Oficinista', personal_bus: 'Personal del bus' }

// Indicadores que ve cada rol (clave del servidor, texto, icono)
const INDICADORES = {
  cooperativa: [
    ['viajes_hoy', 'Viajes programados hoy', 'bus'],
    ['boletos_hoy', 'Boletos vendidos hoy', 'boleto'],
    ['ingresos_hoy', 'Ingresos aprobados hoy', 'dinero'],
    ['pagos_por_validar', 'Pagos por validar', 'tarjeta'],
  ],
  oficinista: [
    ['pagos_por_validar', 'Pagos por validar', 'tarjeta'],
    ['boletos_hoy', 'Boletos vendidos hoy', 'boleto'],
    ['viajes_hoy', 'Viajes programados hoy', 'bus'],
  ],
  personal_bus: [
    ['viajes_hoy', 'Viajes programados hoy', 'bus'],
    ['abordados_hoy', 'Pasajeros abordados hoy', 'qr'],
  ],
}

// Accesos rápidos de cada rol
const ACCESOS = {
  cooperativa: [
    { a: '/cooperativa/hoja-semanal', texto: 'Hoja semanal', detalle: 'Genera los viajes de la semana', icono: 'calendario' },
    { a: '/buses', texto: 'Buses', detalle: 'Flota y mapa de asientos', icono: 'bus' },
    { a: '/frecuencias', texto: 'Frecuencias', detalle: 'Rutas, horarios y precios', icono: 'reloj' },
    { a: '/cooperativa/personal', texto: 'Personal', detalle: 'Oficinistas y choferes', icono: 'usuarios' },
    { a: '/cooperativa/apariencia', texto: 'Apariencia', detalle: 'Logo, colores y eslogan', icono: 'paleta' },
  ],
  oficinista: [
    { a: '/oficinista/vender', texto: 'Vender boletos', detalle: 'Venta en ventanilla, pago en efectivo', icono: 'boleto' },
    { a: '/oficinista/pagos', texto: 'Validar pagos', detalle: 'Revisa los comprobantes de los clientes', icono: 'tarjeta' },
  ],
  personal_bus: [
    { a: '/personal/abordaje', texto: 'Abordaje', detalle: 'Escanea el código QR de cada boleto', icono: 'qr' },
  ],
}

const saludo = () => {
  const hora = Number(new Date().toLocaleString('en-US', { hour: 'numeric', hour12: false, timeZone: 'America/Guayaquil' }))
  return hora < 12 ? 'Buenos días' : hora < 19 ? 'Buenas tardes' : 'Buenas noches'
}

const fechaDeHoy = () => {
  const texto = new Date().toLocaleDateString('es-EC', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Guayaquil' })
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

const valor = (clave, numero) => (clave === 'ingresos_hoy' ? `$${Number(numero || 0).toFixed(2)}` : numero ?? 0)

export default function PanelInicio() {
  const { usuario } = useAuth()
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/panel')
      .then(({ data }) => setDatos(data))
      .catch((err) => setError(mensajeDeError(err)))
  }, [])

  const rol = usuario?.rol
  const ind = datos?.indicadores || {}

  return (
    <div className="container">
      <div className="pagina-encabezado">
        <div>
          <span className="etiqueta-seccion">{fechaDeHoy()}</span>
          <h1>{saludo()}, {usuario?.nombres?.split(' ')[0]}</h1>
          <p>
            {datos?.cooperativa?.nombre ? <><strong>{datos.cooperativa.nombre}</strong> · </> : null}
            {NOMBRE_ROL[rol]}
          </p>
        </div>
        {datos?.cooperativa?.logo_url && (
          <img src={datos.cooperativa.logo_url} alt={`Logo de ${datos.cooperativa.nombre}`}
            style={{ height: 64, maxWidth: 160, objectFit: 'contain', borderRadius: 12, background: '#fff', padding: 6, border: '1px solid var(--borde)' }} />
        )}
      </div>

      {error && <div className="alerta alerta--error" role="alert"><Icono nombre="alerta" /> {error}</div>}

      {/* Avisos que piden una acción */}
      {datos && rol === 'cooperativa' && datos.viajes_manana === 0 && (
        <div className="alerta alerta--aviso">
          <Icono nombre="calendario" />
          <div>
            <strong>Todavía no hay viajes para mañana</strong>
            Genera los viajes desde la <Link to="/cooperativa/hoja-semanal">Hoja semanal</Link> para que los clientes puedan comprar.
          </div>
        </div>
      )}
      {datos && rol === 'oficinista' && ind.pagos_por_validar > 0 && (
        <div className="alerta alerta--info">
          <Icono nombre="tarjeta" />
          <div>
            <strong>{ind.pagos_por_validar} {ind.pagos_por_validar === 1 ? 'pago espera' : 'pagos esperan'} tu revisión</strong>
            Revisa los comprobantes en <Link to="/oficinista/pagos">Validar pagos</Link> para emitir los boletos.
          </div>
        </div>
      )}

      {/* Indicadores del día */}
      {!datos && !error && <div className="cargando"><span className="giro" /> Cargando el resumen del día…</div>}
      {datos && (
        <div className={INDICADORES[rol]?.length === 4 ? 'rejilla-4' : 'rejilla-3'} style={{ marginBottom: '1.5rem' }}>
          {(INDICADORES[rol] || []).map(([clave, texto, icono]) => (
            <div key={clave} className="indicador">
              <span className="indicador__icono"><Icono nombre={icono} tam={22} /></span>
              <div>
                <div className="indicador__valor">{valor(clave, ind[clave])}</div>
                <div className="indicador__texto">{texto}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gap: '1.5rem', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 380px), 1fr))', alignItems: 'start' }}>
        {/* Viajes de hoy */}
        <section className="card" style={{ marginBottom: 0 }}>
          <div className="card-header fila fila--entre">
            <span>Viajes de hoy</span>
            {rol === 'cooperativa' && <Link to="/cooperativa/hojas-ruta" className="btn btn-sm">Ver hojas de ruta</Link>}
          </div>
          {datos && datos.proximos_viajes.length === 0 && (
            <div className="vacio" style={{ border: 0, borderRadius: 0 }}>
              <span className="vacio__icono"><Icono nombre="bus" /></span>
              <h3>No hay viajes programados para hoy</h3>
              {rol === 'cooperativa' && <span>Genéralos desde la Hoja semanal.</span>}
            </div>
          )}
          {datos && datos.proximos_viajes.length > 0 && (
            <div className="table-responsive">
              <table className="table">
                <thead><tr><th>Salida</th><th>Ruta</th><th>Bus</th><th>Ocupación</th></tr></thead>
                <tbody>
                  {datos.proximos_viajes.map((v) => {
                    const porcentaje = v.capacidad ? Math.round((v.vendidos / v.capacidad) * 100) : 0
                    return (
                      <tr key={v.id}>
                        <td><strong>{v.hora_salida}</strong></td>
                        <td>{v.origen} → {v.destino}</td>
                        <td>N.º {v.numero_disco}<div className="texto-suave" style={{ fontSize: '.8rem' }}>{v.placa}</div></td>
                        <td style={{ minWidth: 140 }}>
                          <div style={{ fontSize: '.82rem', fontWeight: 700 }}>{v.vendidos} de {v.capacidad} asientos</div>
                          <div style={{ height: 6, borderRadius: 3, background: 'var(--borde)', marginTop: 4, overflow: 'hidden' }}>
                            <div style={{ width: `${porcentaje}%`, height: '100%', background: 'var(--marca)' }} />
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Accesos rápidos y datos de la flota */}
        <div style={{ display: 'grid', gap: '1rem' }}>
          <section className="card" style={{ marginBottom: 0 }}>
            <div className="card-header">Accesos rápidos</div>
            <div className="card-body" style={{ display: 'grid', gap: '.6rem' }}>
              {(ACCESOS[rol] || []).map((acceso) => (
                <Link key={acceso.a} to={acceso.a} className="btn" style={{ justifyContent: 'flex-start', minHeight: 58, whiteSpace: 'normal', textAlign: 'left' }}>
                  <span className="indicador__icono" style={{ width: 38, height: 38, borderRadius: 11 }}><Icono nombre={acceso.icono} tam={19} /></span>
                  <span style={{ flex: 1 }}>
                    <strong style={{ display: 'block' }}>{acceso.texto}</strong>
                    <span className="texto-suave" style={{ fontSize: '.82rem', fontWeight: 500 }}>{acceso.detalle}</span>
                  </span>
                  <Icono nombre="flecha" tam={18} />
                </Link>
              ))}
            </div>
          </section>

          {rol === 'cooperativa' && datos && (
            <section className="card" style={{ marginBottom: 0 }}>
              <div className="card-header">Tu cooperativa</div>
              <div className="card-body" style={{ display: 'grid', gap: '.6rem' }}>
                {[['buses_activos', 'Buses activos', 'bus'], ['frecuencias_activas', 'Frecuencias activas', 'reloj'], ['personal_activo', 'Personal activo', 'usuarios']].map(([clave, texto, icono]) => (
                  <div key={clave} className="fila fila--entre">
                    <span className="fila" style={{ gap: '.5rem' }}><Icono nombre={icono} tam={18} /> {texto}</span>
                    <strong>{ind[clave]}</strong>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
