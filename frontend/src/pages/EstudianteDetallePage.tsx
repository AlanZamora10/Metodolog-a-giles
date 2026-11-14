import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { DesgloseEstados, EvolucionEstudiante } from '../components/charts/Graficos';
import { EstadoAlertaBadge, EstadoDeActividad, NivelBadge, Vacio } from '../components/ui/ui';
import { actividadesEnCorte, contarEstados, metricasEnCorte, REGLAS } from '../utils/academico';
import { iniciales, nota } from '../utils/formato';

const COMPONENTE: Record<string, string> = { ACD: 'ACD', TAREAS: 'Tarea', PAE: 'PAE' };

/** RF-06: ficha individual del estudiante. */
export function EstudianteDetallePage() {
  return (
    <CursoRequerido>
      <Ficha />
    </CursoRequerido>
  );
}

function Ficha() {
  const { idNumber } = useParams();
  const { datos, corte, alertas } = useCurso();
  const e = datos!.estudiantes.find((x) => x.id_number.toUpperCase() === (idNumber ?? '').toUpperCase());

  const actividades = useMemo(() => (e ? actividadesEnCorte(e, corte) : []), [e, corte]);
  const evolucion = useMemo(
    () =>
      actividades.map((a) => ({
        actividad: a.id_number,
        nota: a.nota,
        nombre: a.nombre ?? a.id_number,
        detalle: `${COMPONENTE[a.componente] ?? a.componente} · Unidad ${a.unidad}`,
      })),
    [actividades],
  );

  if (!e) {
    return (
      <div className="card">
        <Vacio titulo={`El estudiante ${idNumber} no está en ${datos!.shortname}`}>
          <Link className="btn" to="/estudiantes">
            Volver al listado
          </Link>
        </Vacio>
      </div>
    );
  }

  const m = metricasEnCorte(e, corte);
  const estados = contarEstados(actividades);
  const alertasEst = alertas.filter((a) => a.id_number === e.id_number);

  return (
    <>
      <div className="page-head">
        <div className="perfil">
          <div className="avatar" aria-hidden>
            {iniciales(e.nombres)}
          </div>
          <div>
            <h1>{e.nombres}</h1>
            <p>
              {e.id_number} · {e.email} · {datos!.shortname}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link className="btn" to="/estudiantes">
            ← Estudiantes
          </Link>
          {alertasEst.length > 0 && (
            <Link className="btn btn-primary" to={`/alertas?alerta=${alertasEst[0].id}`}>
              Ir a su alerta
            </Link>
          )}
        </div>
      </div>

      <section className="card card-pad">
        {m ? (
          <div className="metricas-mini">
            <div>
              <span>Nota final</span>
              <b>{nota(m.nota_final)}</b> <span style={{ display: 'inline' }}>/10</span>
            </div>
            <div>
              <span>Nivel</span>
              <NivelBadge nivel={m.nivel_riesgo} />
            </div>
            <div>
              <span>ACD (40 %)</span>
              <b>{nota(m.acd)}</b>
            </div>
            <div>
              <span>Tareas (30 %)</span>
              <b>{nota(m.tareas)}</b>
            </div>
            <div>
              <span>PAE (30 %)</span>
              <b>{nota(m.pae)}</b>
            </div>
            <div>
              <span>Tendencia</span>
              <b>
                {m.tendencia === 'SUBE' ? '↗' : m.tendencia === 'BAJA' ? '↘' : '→'} {m.pendiente >= 0 ? '+' : ''}
                {m.pendiente.toFixed(2)}
              </b>
            </div>
            <div>
              <span>Regla de alerta</span>
              <b style={{ fontSize: 13 }}>{e.regla_alerta ? REGLAS[e.regla_alerta] ?? e.regla_alerta : 'Ninguna'}</b>
            </div>
          </div>
        ) : (
          <p className="muted">Sin calificaciones en este corte.</p>
        )}
      </section>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)' }}>
        <section className="card">
          <div className="card-head">
            <h2>Evolución de notas</h2>
            <p>Por actividad, en orden de unidad · los huecos son actividades sin nota</p>
          </div>
          <div className="card-body">
            {evolucion.length ? <EvolucionEstudiante datos={evolucion} /> : <p className="muted">Sin actividades en este corte.</p>}
          </div>
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Desglose de entregas</h2>
            <p>{actividades.length} actividades</p>
          </div>
          <div className="card-body">
            <DesgloseEstados conteo={estados} />
            {m && Object.keys(m.promedios_unidad).length > 0 && (
              <div style={{ marginTop: 18 }}>
                <h3 style={{ marginBottom: 6 }}>Promedio por unidad</h3>
                <table className="tabla">
                  <tbody>
                    {Object.entries(m.promedios_unidad).map(([u, v]) => (
                      <tr key={u}>
                        <td>{u.replace('U', 'Unidad ')}</td>
                        <td className="right num">{nota(v)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Calificaciones por actividad</h2>
          <p>Sincronizadas desde el libro de calificaciones de Moodle UTA</p>
        </div>
        <div className="table-wrap" style={{ marginTop: 10 }}>
          <table className="tabla">
            <thead>
              <tr>
                <th>Código</th>
                <th>Actividad</th>
                <th>Componente</th>
                <th>Unidad</th>
                <th>Parcial</th>
                <th className="right">Nota</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {actividades.map((a) => (
                <tr key={a.id_number}>
                  <td className="mono">{a.id_number}</td>
                  <td>{a.nombre}</td>
                  <td>{COMPONENTE[a.componente] ?? a.componente}</td>
                  <td>U{a.unidad}</td>
                  <td>P{a.parcial}</td>
                  <td className="right num">
                    <strong>{a.nota === null ? '—' : a.nota.toFixed(2)}</strong>
                  </td>
                  <td>
                    <EstadoDeActividad actividad={a} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {alertasEst.length > 0 && (
        <section className="card card-pad">
          <h2 style={{ marginBottom: 8 }}>Alertas del estudiante</h2>
          {alertasEst.map((a) => (
            <div key={a.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '6px 0' }}>
              <EstadoAlertaBadge estado={a.estado} />
              <span className="evidencia">{a.evidencia}</span>
              <Link to={`/alertas?alerta=${a.id}`} style={{ marginLeft: 'auto' }}>
                Abrir
              </Link>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
