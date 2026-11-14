/** RF-11: vista previa del informe académico del curso, descarga en Markdown e impresión/PDF. */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../api/client';
import { endpoints } from '../api/endpoints';
import { useAuth } from '../context/AuthContext';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { DesgloseEstados } from '../components/charts/Graficos';
import { Aviso, NivelBadge } from '../components/ui/ui';
import { REGLAS } from '../utils/academico';
import { fecha, fechaHora, nota } from '../utils/formato';

export function ReportePage() {
  return (
    <CursoRequerido>
      <Informe />
    </CursoRequerido>
  );
}

/** Descarga el informe .md con el JWT (un enlace directo no llevaría la cabecera Authorization). */
export async function descargarMarkdown(courseId: number, nombrePorDefecto: string): Promise<void> {
  const resp = await endpoints.reporteMarkdown(courseId);
  const blob = await resp.blob();
  const cd = resp.headers.get('Content-Disposition') ?? '';
  const nombre = /filename="?([^"]+)"?/.exec(cd)?.[1] ?? nombrePorDefecto;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Informe() {
  const { reporte, cursoId, recargarCurso, cargandoCurso } = useCurso();
  const { usuario } = useAuth();
  const [descargando, setDescargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!reporte) return null;
  const r = reporte;
  const m = r.metricas;
  const d = r.distribucion_estados;

  async function descargar() {
    setDescargando(true);
    setError(null);
    try {
      await descargarMarkdown(cursoId!, `informe_${r.curso.shortname}.md`);
    } catch (ex) {
      setError(ex instanceof ApiError ? ex.detail : 'No se pudo descargar el informe.');
    } finally {
      setDescargando(false);
    }
  }

  return (
    <>
      <div className="page-head no-print">
        <div>
          <h1>Informe del curso</h1>
          <p>Generado por el middleware con datos sincronizados; sin texto inventado.</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn" onClick={recargarCurso} disabled={cargandoCurso}>
            Actualizar
          </button>
          <button className="btn" onClick={descargar} disabled={descargando}>
            {descargando && <span className="spinner" aria-hidden />} Descargar .md
          </button>
          <button className="btn btn-primary" onClick={() => window.print()}>
            Imprimir / guardar PDF
          </button>
        </div>
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}

      <article className="card informe" aria-label="Vista previa del informe">
        <header className="informe-head">
          <div>
            <div className="muted small">Universidad Técnica de Ambato · FISEI · Ingeniería de Software</div>
            <h1 style={{ marginTop: 4 }}>Informe académico — {r.curso.shortname}</h1>
            <p className="muted">{r.curso.fullname}</p>
          </div>
          <dl className="informe-meta">
            <dt>Período</dt>
            <dd>
              {r.periodo.nombre} ({r.periodo.codigo})
            </dd>
            <dt>Vigencia</dt>
            <dd>
              {fecha(r.periodo.inicio)} – {fecha(r.periodo.fin)}
            </dd>
            <dt>Docente</dt>
            <dd>{usuario?.nombres}</dd>
            <dt>Sincronizado</dt>
            <dd>{fechaHora(r.fecha_sincronizacion)}</dd>
            <dt>Generado</dt>
            <dd>{fechaHora(r.generado_en)}</dd>
          </dl>
        </header>

        <section>
          <h2>1. Métricas del curso</h2>
          <div className="metricas-mini">
            <div>
              <span>Estudiantes</span>
              <b>{m.total_estudiantes}</b>
            </div>
            <div>
              <span>Promedio</span>
              <b>{nota(m.promedio)}</b>/10
            </div>
            <div>
              <span>Mediana</span>
              <b>{nota(m.mediana)}</b>
            </div>
            <div>
              <span>Mín. – Máx.</span>
              <b>
                {nota(m.nota_minima)} – {nota(m.nota_maxima)}
              </b>
            </div>
            <div>
              <span>Desv. estándar</span>
              <b>{nota(m.desviacion_estandar)}</b>
            </div>
            <div>
              <span>Aprobación (≥ 7.00)</span>
              <b>{m.porcentaje_aceptables.toFixed(1)} %</b>
            </div>
          </div>
          <div className="grid grid-3" style={{ marginTop: 14 }}>
            <TablaSimple
              titulo="Nivel"
              filas={[
                ['Crítico (< 5.00)', String(m.criticos)],
                ['En riesgo (5.00–6.99)', String(m.en_riesgo)],
                ['Aceptable (≥ 7.00)', String(m.aceptables)],
              ]}
            />
            <TablaSimple
              titulo="Componente"
              filas={[
                ['ACD (40 %)', nota(m.componentes.acd)],
                ['Tareas (30 %)', nota(m.componentes.tareas)],
                ['PAE (30 %)', nota(m.componentes.pae)],
              ]}
            />
            <TablaSimple
              titulo="Unidad"
              filas={Object.entries(m.promedio_por_unidad).map(([u, v]) => [u.replace('U', 'Unidad '), nota(v)])}
            />
          </div>
        </section>

        <section>
          <h2>2. Distribución de estados de las actividades</h2>
          <p className="muted small" style={{ marginBottom: 10 }}>
            {d.total_registros} registros de calificación · {d.estudiantes_con_cero} estudiante(s) con nota cero ·{' '}
            {d.estudiantes_sin_entrega} sin entrega · {d.estudiantes_con_pendiente} con pendientes
          </p>
          <DesgloseEstados conteo={{ calificada: d.calificado, cero: d.cero, sin_entrega: d.sin_entrega, pendiente: d.pendiente }} />
        </section>

        <section>
          <h2>3. Alertas tempranas</h2>
          <p>
            R1 activas: <b>{r.alertas.r1_activas}</b> · R2 activas: <b>{r.alertas.r2_activas}</b> · Abiertas: {r.alertas.abiertas} · En
            atención: {r.alertas.atendidas} · Publicadas: {r.alertas.publicadas} · Cerradas: {r.alertas.cerradas} · Resueltas:{' '}
            {r.alertas.resueltas}
          </p>
          {r.estudiantes_prioritarios.length > 0 && (
            <table className="tabla" style={{ marginTop: 10 }}>
              <thead>
                <tr>
                  <th>Estudiante prioritario</th>
                  <th className="right">Nota final</th>
                  <th>Nivel</th>
                  <th>Regla</th>
                </tr>
              </thead>
              <tbody>
                {r.estudiantes_prioritarios.map((e) => (
                  <tr key={e.id_number}>
                    <td>
                      <Link to={`/estudiantes/${e.id_number}`}>{e.nombres}</Link> <span className="muted small">{e.id_number}</span>
                    </td>
                    <td className="right num">{nota(e.nota_final)}</td>
                    <td>
                      <NivelBadge nivel={e.nivel_riesgo} />
                    </td>
                    <td className="small">{e.regla_alerta ? REGLAS[e.regla_alerta] ?? e.regla_alerta : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section>
          <h2>4. Hallazgos</h2>
          <ul>
            {r.hallazgos.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </section>

        <section>
          <h2>5. Recomendaciones</h2>
          <ul>
            {r.recomendaciones.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </section>

        <footer className="muted small" style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
          EduMonitor AI · Informe determinista calculado a partir del libro de calificaciones de Moodle UTA. Las alertas son señales para
          revisión docente, no calificaciones definitivas.
        </footer>
      </article>
    </>
  );
}

function TablaSimple({ titulo, filas }: { titulo: string; filas: string[][] }) {
  return (
    <table className="tabla">
      <thead>
        <tr>
          <th>{titulo}</th>
          <th className="right">{titulo === 'Nivel' ? 'Estudiantes' : 'Promedio'}</th>
        </tr>
      </thead>
      <tbody>
        {filas.map(([a, b]) => (
          <tr key={a}>
            <td>{a}</td>
            <td className="right num">{b}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
