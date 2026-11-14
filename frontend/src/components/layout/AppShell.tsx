import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCurso } from '../../context/CursoContext';
import { CORTES, type Corte } from '../../utils/academico';
import { fechaHora, haceCuanto, iniciales } from '../../utils/formato';

const NAV = [
  { a: '/dashboard', texto: 'Dashboard', rf: 'RF-05' },
  { a: '/estudiantes', texto: 'Estudiantes', rf: 'RF-04' },
  { a: '/alertas', texto: 'Centro de alertas', rf: 'RF-07' },
  { a: '/agente', texto: 'Agente IA', rf: 'RF-09' },
  { a: '/reporte', texto: 'Informe', rf: 'RF-11' },
];

const ACTIVAS = new Set(['ABIERTA', 'ATENDIDA']);

export function AppShell() {
  const { usuario, cerrarSesion } = useAuth();
  const { alertas } = useCurso();
  const pendientes = alertas.filter((a) => ACTIVAS.has(a.estado)).length;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo" aria-hidden>
            EM
          </div>
          <div>
            <div className="brand-name">EduMonitor AI</div>
            <div className="brand-sub">Moodle UTA · FISEI</div>
          </div>
        </div>
        <nav className="nav" aria-label="Secciones">
          {NAV.map((n) => (
            <NavLink key={n.a} to={n.a}>
              {n.texto}
              {n.a === '/alertas' && pendientes > 0 ? (
                <span className="nav-badge" aria-label={`${pendientes} alertas por atender`}>
                  {pendientes}
                </span>
              ) : (
                <span className="rf">{n.rf}</span>
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
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** Selector de curso, período y corte + estado de sincronización (RF-03, RF-04, RNF-08). */
function BarraSuperior() {
  const c = useCurso();
  const cursos = c.sync?.cursos ?? [];
  const origen = c.sync?.persistencia?.origen === 'restaurado_desde_bd'
    ? `restaurado desde ${c.sync?.persistencia?.motor === 'mssql' ? 'SQL Server' : (c.sync?.persistencia?.motor ?? 'la base')}`
    : c.sync?.moodle?.sitio
      ? `${c.sync.moodle.sitio}${c.sync.moodle.version ? ` ${c.sync.moodle.version.split(' ')[0]}` : ''}`
      : 'Moodle UTA';

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
              {cu.shortname} — {cu.fullname.replace(/^\(SOF\)\s*/, '')}
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
              {p.nombre} ({p.codigo})
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
                    ? `Última sincronización ${haceCuanto(c.sync.ultima_sincronizacion)}`
                    : 'Sin sincronizar'}
                </strong>
              </div>
              <div className="muted">
                {fechaHora(c.sync?.ultima_sincronizacion)} · Origen: {origen}
              </div>
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
