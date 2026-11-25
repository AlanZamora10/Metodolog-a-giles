/** Informe académico del curso con formato institucional UTA - FISEI (blanco y negro): vista previa, .md e impresión/PDF. */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../api/client';
import { endpoints } from '../api/endpoints';
import { useAuth } from '../context/AuthContext';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { Aviso } from '../components/ui/ui';
import { NIVELES, REGLAS } from '../utils/academico';
import { fecha, fechaHora, nota } from '../utils/formato';
import { nombreCurso } from '../utils/nombres';

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

      {/* Documento institucional sobrio (UTA - FISEI): negro sobre blanco y bordes finos, igual en pantalla e impresión */}
      <article className="card informe informe-oficial stagger-1" aria-label="Vista previa del informe">
        <header className="informe-cabecera">
          <img src="/uta-escudo-azul.png" alt="Escudo de la Universidad Técnica de Ambato" className="informe-escudo" />
          <div className="informe-titulos">
            <p className="informe-universidad">UNIVERSIDAD TÉCNICA DE AMBATO</p>
            <p className="informe-facultad">Facultad de Ingeniería en Sistemas, Electrónica e Industrial · Carrera de Software</p>
            <h1>Informe académico — {nombreCurso(r.curso.fullname)}</h1>
          </div>
        </header>

        <table className="informe-tabla informe-datos">
          <tbody>
            <tr>
              <th scope="row">Asignatura</th>
              <td>
                {nombreCurso(r.curso.fullname)} ({r.curso.shortname})
              </td>
              <th scope="row">Docente</th>
              <td>{usuario?.nombres}</td>
            </tr>
            <tr>
              <th scope="row">Período</th>
              <td>
                {r.periodo.nombre} ({r.periodo.codigo})
              </td>
              <th scope="row">Vigencia</th>
              <td>
                {fecha(r.periodo.inicio)} – {fecha(r.periodo.fin)}
              </td>
            </tr>
            <tr>
              <th scope="row">Sincronizado</th>
              <td>{fechaHora(r.fecha_sincronizacion)}</td>
              <th scope="row">Emitido</th>
              <td>{fechaHora(r.generado_en)}</td>
            </tr>
          </tbody>
        </table>

        <section>
          <h2>1. Métricas del curso</h2>
          <table className="informe-tabla informe-metricas">
            <thead>
              <tr>
                <th>Estudiantes</th>
                <th>Promedio</th>
                <th>Mediana</th>
                <th>Mín. – Máx.</th>
                <th>Desv. estándar</th>
                <th>Aprobación</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{m.total_estudiantes}</td>
                <td>{nota(m.promedio)} / 10</td>
                <td>{nota(m.mediana)}</td>
                <td>
                  {nota(m.nota_minima)} – {nota(m.nota_maxima)}
                </td>
                <td>{nota(m.desviacion_estandar)}</td>
                <td>{m.porcentaje_aceptables.toFixed(1)} %</td>
              </tr>
            </tbody>
          </table>
          <div className="informe-columnas">
            <TablaSimple
              titulo="Nivel"
              filas={[
                ['Crítico', String(m.criticos)],
                ['En riesgo', String(m.en_riesgo)],
                ['Aceptable', String(m.aceptables)],
              ]}
            />
            <TablaSimple
              titulo="Componente"
              filas={[
                ['Exámenes (40 %)', nota(m.componentes.acd)],
                ['Tareas (30 %)', nota(m.componentes.tareas)],
                ['APE (30 %)', nota(m.componentes.pae)],
              ]}
            />
            <TablaSimple
              titulo="Unidad"
              filas={Object.entries(m.promedio_por_unidad).map(([u, v]) => [u.replace('U', 'Unidad '), nota(v)])}
            />
          </div>
        </section>

        <section>
          <h2>2. Estado de las actividades</h2>
          <table className="informe-tabla">
            <thead>
              <tr>
                <th>Estado</th>
                <th className="right">Registros</th>
                <th className="right">Estudiantes</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Calificado</td>
                <td className="right">{d.calificado}</td>
                <td className="right">—</td>
              </tr>
              <tr>
                <td>Nota 0</td>
                <td className="right">{d.cero}</td>
                <td className="right">{d.estudiantes_con_cero}</td>
              </tr>
              <tr>
                <td>Sin entrega</td>
                <td className="right">{d.sin_entrega}</td>
                <td className="right">{d.estudiantes_sin_entrega}</td>
              </tr>
              <tr>
                <td>Pendiente de revisión</td>
                <td className="right">{d.pendiente}</td>
                <td className="right">{d.estudiantes_con_pendiente}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <h2>3. Alertas tempranas</h2>
          <table className="informe-tabla">
            <tbody>
              <tr>
                <th scope="row">Nota crítica</th>
                <td className="right">{r.alertas.r1_activas}</td>
                <th scope="row">Descenso sostenido</th>
                <td className="right">{r.alertas.r2_activas}</td>
              </tr>
              <tr>
                <th scope="row">Abiertas / en atención</th>
                <td className="right">
                  {r.alertas.abiertas} / {r.alertas.atendidas}
                </td>
                <th scope="row">Publicadas / cerradas / resueltas</th>
                <td className="right">
                  {r.alertas.publicadas} / {r.alertas.cerradas} / {r.alertas.resueltas}
                </td>
              </tr>
            </tbody>
          </table>
          {r.estudiantes_prioritarios.length > 0 && (
            <table className="informe-tabla" style={{ marginTop: 10 }}>
              <thead>
                <tr>
                  <th>Estudiante prioritario</th>
                  <th className="right">Nota final</th>
                  <th>Nivel</th>
                  <th>Alerta</th>
                </tr>
              </thead>
              <tbody>
                {r.estudiantes_prioritarios.map((e) => (
                  <tr key={e.id_number}>
                    <td>
                      <Link to={`/estudiantes/${e.id_number}`}>{e.nombres}</Link>
                    </td>
                    <td className="right">{nota(e.nota_final)}</td>
                    <td>{NIVELES[e.nivel_riesgo]?.etiqueta ?? e.nivel_riesgo}</td>
                    <td>{e.regla_alerta ? REGLAS[e.regla_alerta] ?? e.regla_alerta : '—'}</td>
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
      </article>
    </>
  );
}

function TablaSimple({ titulo, filas }: { titulo: string; filas: string[][] }) {
  return (
    <table className="informe-tabla">
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
            <td className="right">{b}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
