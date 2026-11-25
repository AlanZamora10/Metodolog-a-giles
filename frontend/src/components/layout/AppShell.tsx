import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCurso } from '../../context/CursoContext';
import { CORTES, type Corte } from '../../utils/academico';
import { fechaHora, haceCuanto, iniciales } from '../../utils/formato';
import { nombreCurso } from '../../utils/nombres';

const NAV = [
  { a: '/dashboard', texto: 'Dashboard' },
  { a: '/estudiantes', texto: 'Estudiantes' },
  { a: '/alertas', texto: 'Centro de alertas' },
  { a: '/agente', texto: 'Agente IA' },
  { a: '/reporte', texto: 'Informe' },
];

const ACTIVAS = new Set(['ABIERTA', 'ATENDIDA']);

export function AppShell() {
  const { usuario, cerrarSesion } = useAuth();
  const { alertas } = useCurso();
  const { pathname } = useLocation();
  const pendientes = alertas.filter((a) => ACTIVAS.has(a.estado)).length;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <img src="/uta-escudo-blanco.png" alt="Escudo de la Universidad Técnica de Ambato" className="brand-escudo" />
          <div>
            <div className="brand-name">CoraIA</div>
            <div className="brand-sub">UTA · FISEI</div>
          </div>
        </div>
        <nav className="nav" aria-label="Secciones">
          {NAV.map((n) => (
            <NavLink key={n.a} to={n.a}>
              {n.texto}
              {n.a === '/alertas' && pendientes > 0 && (
                <span className="nav-badge" aria-label={`${pendientes} alertas por atender`}>
                  {pendientes}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="avatar" aria-hidden>
            {iniciales(usuario?.nombres ?? '')}
          </div>
          <div className="who">
            <div style={{ fontWeight: 600 }}>{usuario?.nombres}</div>
            <div className="small" style={{ opacity: 0.75 }}>
              {usuario?.email}
            </div>
          </div>
          <button className="btn-salir" onClick={() => cerrarSesion()}>
            Salir
          </button>
        </div>
      </aside>
      <div className="main">
        <BarraSuperior />
        <main className={`content${pathname.startsWith('/agente') ? ' content-chat' : ''}`}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** Selector de curso, período y corte + estado de sincronización. */
function BarraSuperior() {
  const c = useCurso();
  const cursos = c.sync?.cursos ?? [];

  return (
    <header className="topbar">
      <label className="field">
        <span>Curso</span>
        <select
          className="select curso"
          value={c.cursoId ?? ''}
          onChange={(e) => c.seleccionarCurso(Number(e.target.value))}
          disabled={!cursos.length}
          aria-label="Curso"
        >
          {!cursos.length && <option value="">Sin cursos sincronizados</option>}
          {cursos.map((cu) => (
            <option key={cu.id} value={cu.id}>
              {nombreCurso(cu.fullname)}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Período académico</span>
        <select
          className="select"
          value={c.periodo ?? ''}
          onChange={(e) => c.seleccionarPeriodo(e.target.value)}
          disabled={!c.periodos.length}
          aria-label="Período académico"
        >
          {!c.periodos.length && <option value="">—</option>}
          {c.periodos.map((p) => (
            <option key={p.codigo} value={p.codigo}>
              {p.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Corte</span>
        <select className="select" value={c.corte} onChange={(e) => c.seleccionarCorte(e.target.value as Corte)} aria-label="Corte de evaluación">
          {CORTES.map((k) => (
            <option key={k.valor} value={k.valor}>
              {k.etiqueta}
            </option>
          ))}
        </select>
      </label>

      <div className="sync-box">
        <div className="sync-info" aria-live="polite">
          {c.estadoSync === 'sincronizando' ? (
            <div>
              <span className="dot run" />
              <strong>Sincronizando con Moodle UTA…</strong>
            </div>
          ) : c.estadoSync === 'error' ? (
            <div style={{ color: 'var(--red)' }}>
              <span className="dot err" />
              <strong>Error de sincronización</strong>
              <div className="small">{c.errorSync}</div>
            </div>
          ) : (
            <>
              <div>
                <span className={`dot ${c.sync?.ultima_sincronizacion ? 'ok' : 'err'}`} />
                <strong>
                  {c.sync?.ultima_sincronizacion
                    ? `Sincronizado ${haceCuanto(c.sync.ultima_sincronizacion)}`
                    : 'Sin sincronizar'}
                </strong>
              </div>
              <div className="muted">{fechaHora(c.sync?.ultima_sincronizacion)}</div>
            </>
          )}
        </div>
        <button className="btn btn-primary" onClick={() => c.sincronizar()} disabled={c.estadoSync === 'sincronizando'}>
          {c.estadoSync === 'sincronizando' ? <span className="spinner" aria-hidden /> : '⟳'} Sincronizar
        </button>
      </div>
    </header>
  );
}
