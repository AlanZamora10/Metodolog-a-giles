import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { BarrasPromedio, DesgloseEstados, DistribucionNotas } from '../components/charts/Graficos';
import { KpiCard, NivelBadge } from '../components/ui/ui';
import {
  CORTES,
  actividadesEnCorte,
  contarEstados,
  histograma,
  metricasEnCorte,
  promedioPorActividad,
  promedioPorComponente,
  promedioPorUnidad,
  resumenGrupo,
} from '../utils/academico';
import { nota } from '../utils/formato';

const ACTIVAS = new Set(['ABIERTA', 'ATENDIDA', 'PUBLICADO']);

/** RF-05 / RF-08: dashboard académico grupal. */
export function DashboardPage() {
  return (
    <CursoRequerido>
      <Dashboard />
    </CursoRequerido>
  );
}

function Dashboard() {
  const { datos, alertas, corte, reporte } = useCurso();
  const estudiantes = datos!.estudiantes;
  const etiquetaCorte = CORTES.find((c) => c.valor === corte)!.etiqueta;

  const r = useMemo(() => resumenGrupo(estudiantes, corte), [estudiantes, corte]);
  const notas = useMemo(
    () => estudiantes.map((e) => metricasEnCorte(e, corte)?.nota_final).filter((n): n is number => n !== undefined),
    [estudiantes, corte],
  );
  const unidades = useMemo(() => promedioPorUnidad(estudiantes, corte), [estudiantes, corte]);
  const actividades = useMemo(
    () => promedioPorActividad(estudiantes, corte).map((a) => ({ ...a, detalle: a.actividad })),
    [estudiantes, corte],
  );
  const componentes = useMemo(() => promedioPorComponente(estudiantes, corte), [estudiantes, corte]);
  const estados = useMemo(() => contarEstados(estudiantes.flatMap((e) => actividadesEnCorte(e, corte))), [estudiantes, corte]);
  const activas = alertas.filter((a) => ACTIVAS.has(a.estado));
  const prioritarios = useMemo(
    () =>
      estudiantes
        .map((e) => ({ e, m: metricasEnCorte(e, corte) }))
        .filter((x) => x.m && x.m.nota_final < 7)
        .sort((a, b) => a.m!.nota_final - b.m!.nota_final)
        .slice(0, 6),
    [estudiantes, corte],
  );

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{datos!.shortname}</h1>
          <p>
            {datos!.fullname} · {etiquetaCorte}
          </p>
        </div>
        <Link className="btn" to="/reporte">
          Ver informe del curso
        </Link>
      </div>

      <div className="grid grid-4">
        <KpiCard
          etiqueta="Promedio general"
          valor={r.promedio === null ? '—' : r.promedio.toFixed(2)}
          unidad="/10"
          detalle={`${r.evaluados} de ${r.total} estudiantes con notas en el corte`}
        />
        <KpiCard etiqueta="Total de estudiantes" valor={r.total} detalle={`${r.niveles.CRITICO} crítico(s) · ${r.niveles.EN_RIESGO} en riesgo`} />
        <KpiCard
          etiqueta="Tasa de aprobación"
          valor={r.tasaAprobacion === null ? '—' : r.tasaAprobacion.toFixed(1)}
          unidad="%"
          detalle={`${r.aprobados} estudiante(s) con nota ≥ 7.00`}
        />
        <KpiCard
          etiqueta="Alertas activas"
          valor={activas.length}
          detalle={
            <>
              {alertas.filter((a) => a.estado === 'ABIERTA').length} abiertas · {alertas.filter((a) => a.estado === 'PUBLICADO').length} con refuerzo publicado
            </>
          }
        />
      </div>

      <div className="grid grid-2">
        <section className="card">
          <div className="card-head">
            <h2>Distribución de calificaciones</h2>
            <p>Estudiantes por tramo de nota final</p>
          </div>
          <div className="card-body">
            <DistribucionNotas datos={histograma(notas)} />
          </div>
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Rendimiento por unidad</h2>
            <p>Promedio del grupo /10</p>
          </div>
          <div className="card-body">
            {unidades.length ? <BarrasPromedio datos={unidades} clave="unidad" /> : <p className="muted">Sin notas en este corte.</p>}
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Rendimiento por actividad</h2>
          <p>Promedio del grupo en cada actividad calificada (U = unidad, A = ACD, T = tarea, P = PAE)</p>
        </div>
        <div className="card-body">
          {actividades.length ? (
            <BarrasPromedio datos={actividades} clave="actividad" alto={280} />
          ) : (
            <p className="muted">Sin actividades calificadas en este corte.</p>
          )}
        </div>
      </section>

      <div className="grid grid-3">
        <section className="card">
          <div className="card-head">
            <h2>Componentes</h2>
            <p>ACD 40 % · Tareas 30 % · PAE 30 %</p>
          </div>
          <div className="card-body">
            <BarrasPromedio datos={componentes} clave="componente" alto={220} />
          </div>
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Estado de las entregas</h2>
            <p>{Object.values(estados).reduce((s, n) => s + n, 0)} registros</p>
          </div>
          <div className="card-body">
            <DesgloseEstados conteo={estados} />
          </div>
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Requieren seguimiento</h2>
            <p>Nota &lt; 7.00</p>
          </div>
          <div className="card-body" style={{ paddingTop: 4 }}>
            {prioritarios.length === 0 && <p className="muted">Todos los estudiantes tienen nota ≥ 7.00.</p>}
            <table className="tabla">
              <tbody>
                {prioritarios.map(({ e, m }) => (
                  <tr key={e.id_number}>
                    <td>
                      <Link to={`/estudiantes/${e.id_number}`}>{e.nombres}</Link>
                    </td>
                    <td className="right num">{nota(m!.nota_final)}</td>
                    <td className="right">
                      <NivelBadge nivel={m!.nivel_riesgo} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {reporte && corte === 'periodo' && reporte.hallazgos.length > 0 && (
        <section className="card card-pad">
          <h2 style={{ marginBottom: 8 }}>Hallazgos del período</h2>
          <ul style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 4 }}>
            {reporte.hallazgos.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
