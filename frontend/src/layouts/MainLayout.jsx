import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useConfiguracion } from '../hooks/useConfiguracion.js'
import { useAuth } from '../context/AuthContext.jsx'
import PieDePagina from '../components/PieDePagina.jsx'
import Notificaciones from '../components/Notificaciones.jsx'
import Icono from '../components/Icono.jsx'

/*
  Diseño general de la aplicación (CC-19).
  - Visitantes y clientes: barra superior con el buscador de pasajes.
  - Personal (admin, cooperativa, oficinista, personal del bus): panel con menú lateral.
*/

const NOMBRE_ROL = {
  admin: 'Administrador',
  cooperativa: 'Cooperativa',
  oficinista: 'Oficinista',
  personal_bus: 'Personal del bus',
  cliente: 'Cliente',
}

// Menú lateral de cada rol, agrupado por secciones
const MENU = {
  admin: [
    { grupo: 'Administración', enlaces: [
      { a: '/cooperativas', texto: 'Cooperativas', icono: 'edificio' },
      { a: '/admin/usuarios', texto: 'Usuarios y roles', icono: 'usuarios' },
      { a: '/admin/configuracion', texto: 'Configuración', icono: 'ajustes' },
    ] },
  ],
  cooperativa: [
    // GC-9: panel de inicio
    { grupo: 'General', enlaces: [{ a: '/panel', texto: 'Inicio', icono: 'inicio' }] },
    { grupo: 'Flota', enlaces: [
      { a: '/buses', texto: 'Buses', icono: 'bus' },
      { a: '/cooperativa/tipos-asiento', texto: 'Tipos de asiento', icono: 'asiento' },
    ] },
    { grupo: 'Operación', enlaces: [
      { a: '/frecuencias', texto: 'Frecuencias', icono: 'reloj' },
      { a: '/cooperativa/hojas-ruta', texto: 'Hojas de ruta', icono: 'ruta' },
      { a: '/cooperativa/turnos', texto: 'Turnos', icono: 'capas' },
      { a: '/cooperativa/hoja-semanal', texto: 'Hoja semanal', icono: 'calendario' },
    ] },
    { grupo: 'Mi cooperativa', enlaces: [
      { a: '/cooperativa/personal', texto: 'Personal', icono: 'usuarios' },
      { a: '/cooperativa/apariencia', texto: 'Apariencia', icono: 'paleta' },
    ] },
  ],
  oficinista: [
    // GC-9: panel de inicio
    { grupo: 'General', enlaces: [{ a: '/panel', texto: 'Inicio', icono: 'inicio' }] },
    { grupo: 'Ventanilla', enlaces: [
      { a: '/oficinista/vender', texto: 'Vender boletos', icono: 'boleto' },
      { a: '/oficinista/pagos', texto: 'Validar pagos', icono: 'tarjeta' },
    ] },
  ],
  personal_bus: [
    // GC-9: panel de inicio
    { grupo: 'General', enlaces: [{ a: '/panel', texto: 'Inicio', icono: 'inicio' }] },
    { grupo: 'En el bus', enlaces: [
      { a: '/personal/abordaje', texto: 'Abordaje', icono: 'qr' },
    ] },
  ],
}

const iniciales = (u) => `${u?.nombres?.[0] || ''}${u?.apellidos?.[0] || ''}`.toUpperCase() || 'U'

// Datos de la cooperativa del usuario (los publica TemaCooperativa, CC-24)
const leerCooperativa = () => (typeof window !== 'undefined' ? window.__aparienciaCooperativa || null : null)

function MainLayout() {
  const { usuario, cerrarSesion } = useAuth()
  const configuracion = useConfiguracion()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [cooperativa, setCooperativa] = useState(leerCooperativa)

  // Recarga la app en /login: así el próximo inicio de sesión
  // no intenta volver a una página de otro rol.
  const salir = () => {
    cerrarSesion()
    window.location.href = '/login'
  }

  useEffect(() => {
    const alCambiarApariencia = () => setCooperativa(leerCooperativa())
    // api.js avisa cuando el servidor rechaza el token (sesión vencida)
    const alExpirar = () => {
      cerrarSesion()
      navigate('/login', { replace: true, state: { expirada: true } })
    }
    window.addEventListener('apariencia-cooperativa', alCambiarApariencia)
    window.addEventListener('sesion-expirada', alExpirar)
    return () => {
      window.removeEventListener('apariencia-cooperativa', alCambiarApariencia)
      window.removeEventListener('sesion-expirada', alExpirar)
    }
  }, [cerrarSesion, navigate])

  const marca = (
    <Link to="/" className="marca">
      {configuracion.logo_url
        ? <img src={configuracion.logo_url} alt="" className="marca__logo" />
        : <span className="marca__icono"><Icono nombre="bus" tam={20} /></span>}
      <span>{configuracion.nombre_app}</span>
    </Link>
  )

  const menu = usuario ? MENU[usuario.rol] : null

  // ── Panel del personal ──────────────────────────────────────────────
  if (menu) {
    const actual = menu.flatMap((g) => g.enlaces).find((e) => location.pathname.startsWith(e.a))
    return (
      <div className="app">
        <aside className={`app__lateral ${menuAbierto ? 'abierto' : ''}`} aria-label="Menú principal">
          <div className="app__lateral-cabecera">
            {marca}
            <button type="button" className="btn btn--fantasma btn--icono solo-movil" style={{ color: '#fff' }}
              onClick={() => setMenuAbierto(false)} aria-label="Cerrar menú">
              <Icono nombre="cerrar" />
            </button>
          </div>

          {cooperativa && usuario.cooperativa_id && (
            <div className="app__cooperativa">
              {cooperativa.logo_url
                ? <img src={cooperativa.logo_url} alt="" />
                : <span className="marca__icono"><Icono nombre="edificio" tam={18} /></span>}
              <div>
                <strong>{cooperativa.nombre}</strong>
                <span>{cooperativa.eslogan || NOMBRE_ROL[usuario.rol]}</span>
              </div>
            </div>
          )}

          <nav className="app__navegacion">
            {menu.map((seccion) => (
              <div key={seccion.grupo}>
                <div className="app__grupo">{seccion.grupo}</div>
                {seccion.enlaces.map((e) => (
                  <NavLink key={e.a} to={e.a} onClick={() => setMenuAbierto(false)}
                    className={({ isActive }) => `app__enlace ${isActive ? 'activo' : ''}`}>
                    <Icono nombre={e.icono} />
                    {e.texto}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>

          <div className="app__pie-lateral">
            <div className="app__usuario">
              <span className="avatar">{iniciales(usuario)}</span>
              <div>
                <strong>{usuario.nombres} {usuario.apellidos}</strong>
                <span>{NOMBRE_ROL[usuario.rol]}</span>
              </div>
            </div>
            <button type="button" className="app__salir" onClick={salir}>
              <Icono nombre="salir" tam={18} /> Cerrar sesión
            </button>
          </div>
        </aside>
        {menuAbierto && <div className="app__fondo-movil" onClick={() => setMenuAbierto(false)} />}

        <div className="app__principal">
          <header className="app__superior">
            <button type="button" className="btn btn--icono solo-movil" onClick={() => setMenuAbierto(true)} aria-label="Abrir menú">
              <Icono nombre="menu" />
            </button>
            <div className="app__superior-titulo">
              <span>{NOMBRE_ROL[usuario.rol]} / </span>{actual?.texto || 'Panel'}
            </div>
            <div className="app__superior-acciones">
              <Notificaciones />
            </div>
          </header>
          <main className="app__contenido">
            <Outlet />
          </main>
        </div>
      </div>
    )
  }

  // ── Sitio público y clientes ────────────────────────────────────────
  const anchoCompleto = location.pathname === '/' || location.pathname === '/login' || location.pathname === '/registro'
  return (
    <div className="sitio">
      <header className="sitio__barra">
        <div className="sitio__barra-interior">
          {marca}
          <nav className="sitio__nav">
            <NavLink to="/viajes" className={({ isActive }) => `sitio__enlace ${isActive ? 'activo' : ''}`}>
              <Icono nombre="buscar" tam={18} /><span className="oculto-movil">Buscar pasajes</span>
            </NavLink>
            {usuario?.rol === 'cliente' && (
              <NavLink to="/mis-boletos" className={({ isActive }) => `sitio__enlace ${isActive ? 'activo' : ''}`}>
                <Icono nombre="boleto" tam={18} /><span className="oculto-movil">Mis boletos</span>
              </NavLink>
            )}
            {usuario ? (
              <>
                <Notificaciones />
                <MenuUsuario usuario={usuario} onSalir={salir} />
              </>
            ) : (
              <>
                <Link to="/login" className="sitio__enlace">Iniciar sesión</Link>
                <Link to="/registro" className="btn btn-primary btn--sm">Crear cuenta</Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className={`sitio__contenido ${anchoCompleto ? 'sitio__contenido--ancho' : ''}`}>
        <Outlet />
      </main>
      <PieDePagina configuracion={configuracion} />
    </div>
  )
}

// Botón con el nombre del usuario y su menú desplegable
function MenuUsuario({ usuario, onSalir }) {
  const [abierto, setAbierto] = useState(false)
  const caja = useRef(null)

  useEffect(() => {
    if (!abierto) return
    const fuera = (e) => { if (caja.current && !caja.current.contains(e.target)) setAbierto(false) }
    document.addEventListener('mousedown', fuera)
    return () => document.removeEventListener('mousedown', fuera)
  }, [abierto])

  return (
    <div className="menu-usuario" ref={caja}>
      <button type="button" className="menu-usuario__boton" onClick={() => setAbierto(!abierto)} aria-expanded={abierto}>
        <span className="avatar">{iniciales(usuario)}</span>
        <span className="menu-usuario__nombre oculto-movil">{usuario.nombres}</span>
      </button>
      {abierto && (
        <div className="desplegable">
          <div className="desplegable__cabecera">
            <strong>{usuario.nombres} {usuario.apellidos}</strong>
            <span>{usuario.email}</span>
          </div>
          <Link to="/mis-boletos" className="desplegable__opcion" onClick={() => setAbierto(false)}>
            <Icono nombre="boleto" tam={18} /> Mis boletos
          </Link>
          <Link to="/viajes" className="desplegable__opcion" onClick={() => setAbierto(false)}>
            <Icono nombre="buscar" tam={18} /> Buscar pasajes
          </Link>
          <button type="button" className="desplegable__opcion desplegable__opcion--peligro" onClick={onSalir}>
            <Icono nombre="salir" tam={18} /> Cerrar sesión
          </button>
        </div>
      )}
    </div>
  )
}

export default MainLayout
