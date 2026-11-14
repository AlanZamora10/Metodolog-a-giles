import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { EstadoActividadBadge, NivelBadge } from '../components/ui/ui';
import { actividadesEnCorte, contarEstados, metricasEnCorte, REGLAS } from '../utils/academico';
import { nota } from '../utils/formato';

/** RF-04: listado de estudiantes del curso con buscador y filtros. */
export function EstudiantesPage() {
  return (
    <CursoRequerido>
      <Listado />
    </CursoRequerido>
  );
}

const normalizar = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

function Listado() {
  const { datos, corte } = useCurso();
  const navegar = useNavigate();
  const [busqueda, setBusqueda] = useState('');
  const [nivel, setNivel] = useState('');
  const [regla, setRegla] = useState('');
  const [conIncidencias, setConIncidencias] = useState(false);

  const filas = useMemo(() => {
    const q = normalizar(busqueda.trim());
    return datos!.estudiantes
      .map((e) => {
        const m = metricasEnCorte(e, corte);
        const estados = contarEstados(actividadesEnCorte(e, corte));
        return { e, m, estados, incidencias: estados.cero + estados.sin_entrega + estados.pendiente };
      })
      .filter(({ e, m, incidencias }) => {
        if (q && !normalizar(`${e.nombres} ${e.id_number} ${e.email}`).includes(q)) return false;
        if (nivel && m?.nivel_riesgo !== nivel) return false;
        if (regla === 'ninguna' ? e.regla_alerta : regla && e.regla_alerta !== regla) return false;
        if (conIncidencias && incidencias === 0) return false;
        return true;
      })
      .sort((a, b) => a.e.nombres.localeCompare(b.e.nombres, 'es'));
  }, [datos, corte, busqueda, nivel, regla, conIncidencias]);

  const limpiar = () => {
    setBusqueda('');
    setNivel('');
    setRegla('');
    setConIncidencias(false);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Estudiantes</h1>
          <p>
            {datos!.shortname} · {datos!.estudiantes.length} matriculados en Moodle UTA
          </p>
        </div>
      </div>

      <section className="card">
        <div className="card-body filtros" style={{ paddingTop: 16 }}>
          <label className="field">
            <span>Buscar</span>
            <input
              className="input buscar"
              type="search"
              placeholder="Nombre, código (U-04) o correo"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Nivel</span>
            <select className="select" value={nivel} onChange={(e) => setNivel(e.target.value)}>
              <option value="">Todos</option>
              <option value="CRITICO">Crítico (&lt; 5.00)</option>
              <option value="EN_RIESGO">En riesgo (5.00–6.99)</option>
              <option value="ACEPTABLE">Aceptable (≥ 7.00)</option>
            </select>
          </label>
          <label className="field">
            <span>Regla de alerta</span>
            <select className="select" value={regla} onChange={(e) => setRegla(e.target.value)}>
              <option value="">Todas</option>
              <option value="R1_NOTA_CRITICA">R1 · nota crítica</option>
              <option value="R2_DESCENSO">R2 · descenso</option>
              <option value="ninguna">Sin alerta</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={conIncidencias} onChange={(e) => setConIncidencias(e.target.checked)} />
            Con incidencias (cero, sin entrega, pendiente)
          </label>
          <button className="btn btn-sm" onClick={limpiar} style={{ marginLeft: 'auto' }}>
            Limpiar filtros
          </button>
        </div>

        <div className="table-wrap">
          <table className="tabla">
            <thead>
              <tr>
                <th>Estudiante</th>
                <th className="right">ACD</th>
                <th className="right">Tareas</th>
                <th className="right">PAE</th>
                <th className="right">Nota final</th>
                <th>Nivel</th>
                <th>Tendencia</th>
                <th>Incidencias</th>
                <th>Alerta</th>
              </tr>
            </thead>
            <tbody>
              {filas.map(({ e, m, estados }) => (
                <tr key={e.id_number} className="clickable" onClick={() => navegar(`/estudiantes/${e.id_number}`)}>
                  <td>
                    <div className="nombre-cell">
                      <a
                        href={`/estudiantes/${e.id_number}`}
                        onClick={(ev) => {
                          ev.preventDefault();
                        }}
                      >
                        {e.nombres}
                      </a>
                      <span>
                        {e.id_number} · {e.email}
                      </span>
                    </div>
                  </td>
                  <td className="right num">{nota(m?.acd)}</td>
                  <td className="right num">{nota(m?.tareas)}</td>
                  <td className="right num">{nota(m?.pae)}</td>
                  <td className="right num">
                    <strong>{nota(m?.nota_final)}</strong>
                  </td>
                  <td>{m ? <NivelBadge nivel={m.nivel_riesgo} /> : <span className="muted">Sin notas</span>}</td>
                  <td className="small">
                    {m ? `${m.tendencia === 'SUBE' ? '↗' : m.tendencia === 'BAJA' ? '↘' : '→'} ${m.tendencia.toLowerCase()} (${m.pendiente >= 0 ? '+' : ''}${m.pendiente.toFixed(2)})` : '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {estados.cero > 0 && <EstadoActividadBadge estado="cero" />}
                      {estados.sin_entrega > 0 && <EstadoActividadBadge estado="sin_entrega" />}
                      {estados.pendiente > 0 && <EstadoActividadBadge estado="pendiente" />}
                      {estados.cero + estados.sin_entrega + estados.pendiente === 0 && <span className="muted small">Ninguna</span>}
                    </div>
                  </td>
                  <td className="small">{e.regla_alerta ? REGLAS[e.regla_alerta] ?? e.regla_alerta : <span className="muted">—</span>}</td>
                </tr>
              ))}
              {filas.length === 0 && (
                <tr>
                  <td colSpan={9} className="muted" style={{ textAlign: 'center', padding: 28 }}>
                    Ningún estudiante coincide con los filtros.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="card-body small muted">
          Mostrando {filas.length} de {datos!.estudiantes.length} estudiantes.
        </div>
      </section>
    </>
  );
}
