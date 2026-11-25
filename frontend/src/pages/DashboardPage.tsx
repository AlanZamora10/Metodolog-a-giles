import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { BarrasPromedio, DesgloseEstados, DistribucionNotas, LeyendaReferencias } from '../components/charts/Graficos';
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
import { nombreCurso } from '../utils/nombres';

const ACTIVAS = new Set(['ABIERTA', 'ATENDIDA', 'PUBLICADO']);

/** Pestañas de «Rendimiento por actividad»: el código U<n>-<letra><n> indica el tipo de actividad. */
type TipoActividad = 'todas' | 'A' | 'T' | 'P';
const TIPOS_ACTIVIDAD: { valor: TipoActividad; etiqueta: string }[] = [
  { valor: 'todas', etiqueta: 'Todas' },
  { valor: 'A', etiqueta: 'Exámenes (A)' },
  { valor: 'T', etiqueta: 'Tareas (T)' },
  { valor: 'P', etiqueta: 'Prácticas APE (P)' },
];

function tipoDeActividad(codigo: string): 'A' | 'T' | 'P' | null {
  const m = /-([ATP])\d/i.exec(codigo);
  return m ? (m[1].toUpperCase() as 'A' | 'T' | 'P') : null;
}

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

function mediana(v: number[]): number | null {
  if (!v.length) return null;
  const o = [...v].sort((a, b) => a - b);
  const m = Math.floor(o.length / 2);
  return o.length % 2 ? o[m] : (o[m - 1] + o[m]) / 2;
}

const nombreUnidad = (u: string) => u.replace(/^U(\d+)$/, 'Unidad $1');
const listaNombres = (n: string[]) => (n.length <= 1 ? n.join('') : `${n.slice(0, -1).join(', ')} y ${n[n.length - 1]}`);

/** Tarjeta minimalista de un hallazgo (título + líneas cortas). */
function Hallazgo({ titulo, children, testid }: { titulo: string; children: React.ReactNode; testid: string }) {
  return (
    <article className="hallazgo" data-testid={testid}>
      <h3>{titulo}</h3>
      <div className="hallazgo-cuerpo">{children}</div>
    </article>
  );
}

/** Dashboard académico grupal. */
export function DashboardPage() {
  return (
    <CursoRequerido>
      <Dashboard />
    </CursoRequerido>
  );
}

function Dashboard() {
  const { datos, alertas, corte } = useCurso();
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
  const [tipo, setTipo] = useState<TipoActividad>('todas');
  const actividadesVisibles = useMemo(
    () => (tipo === 'todas' ? actividades : actividades.filter((a) => tipoDeActividad(a.actividad) === tipo)),
    [actividades, tipo],
  );
  const componentes = useMemo(() => promedioPorComponente(estudiantes, corte), [estudiantes, corte]);
  const estados = useMemo(() => contarEstados(estudiantes.flatMap((e) => actividadesEnCorte(e, corte))), [estudiantes, corte]);
  const activas = alertas.filter((a) => ACTIVAS.has(a.estado));
  const criticos = useMemo(
    () => estudiantes.filter((e) => metricasEnCorte(e, corte)?.nivel_riesgo === 'CRITICO').map((e) => e.nombres),
    [estudiantes, corte],
  );
  const descenso = useMemo(
    () => estudiantes.filter((e) => e.regla_alerta === 'R2_DESCENSO').map((e) => e.nombres),
    [estudiantes],
  );
  const menorComponente = useMemo(
    () => [...componentes].filter((c) => c.promedio > 0).sort((a, b) => a.promedio - b.promedio)[0],
    [componentes],
  );
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
          <h1>{nombreCurso(datos!.fullname)}</h1>
          <p>{etiquetaCorte}</p>
        </div>
        <Link className="btn" to="/reporte">
          Ver informe del curso
        </Link>
      </div>

      <div className="grid grid-4">
        <KpiCard
          className="stagger-1"
          etiqueta="Promedio general"
          valor={r.promedio === null ? '—' : r.promedio.toFixed(2)}
          unidad="/10"
          detalle={`${r.evaluados} de ${r.total} estudiantes con notas en el corte`}
        />
        <KpiCard className="stagger-2" etiqueta="Total de estudiantes" valor={r.total} detalle={`${plural(r.niveles.CRITICO, 'crítico', 'críticos')} · ${r.niveles.EN_RIESGO} en riesgo`} />
        <KpiCard
          className="stagger-3"
          etiqueta="Tasa de aprobación"
          valor={r.tasaAprobacion === null ? '—' : r.tasaAprobacion.toFixed(1)}
          unidad="%"
          detalle={plural(r.aprobados, 'estudiante aprobado', 'estudiantes aprobados')}
        />
        <KpiCard
          className="stagger-4"
          etiqueta="Alertas activas"
          valor={activas.length}
          detalle={
            <>
              {alertas.filter((a) => a.estado === 'ABIERTA').length} abiertas · {alertas.filter((a) => a.estado === 'PUBLICADO').length} con refuerzo publicado
            </>
          }
        />
      </div>

      <div className="grid grid-2 stagger-5">
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
            <div className="card-titulo">
              <h2>Rendimiento por unidad</h2>
              <p>Promedio del grupo /10</p>
            </div>
            <LeyendaReferencias />
          </div>
          <div className="card-body">
            {unidades.length ? <BarrasPromedio datos={unidades} clave="unidad" /> : <p className="muted">Sin notas en este corte.</p>}
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <div className="card-titulo">
            <h2>Rendimiento por actividad</h2>
            <p>Promedio del grupo /10 en cada actividad calificada</p>
          </div>
          <div className="card-extra">
            <div className="tabs-actividad" role="tablist" aria-label="Tipo de actividad">
              {TIPOS_ACTIVIDAD.map((t) => (
                <button
                  key={t.valor}
                  type="button"
                  role="tab"
                  aria-selected={tipo === t.valor}
                  onClick={() => setTipo(t.valor)}
                >
                  {t.etiqueta}
                </button>
              ))}
            </div>
            <LeyendaReferencias />
          </div>
        </div>
        <div className="card-body">
          <p className="leyenda-codigos" data-testid="leyenda-codigos">
            <span><b>U</b> = Unidad</span>
            <span><b>A</b> = Examen</span>
            <span><b>T</b> = Tarea</span>
            <span><b>P</b> = Práctica APE</span>
          </p>
          {actividadesVisibles.length ? (
            <BarrasPromedio datos={actividadesVisibles} clave="actividad" alto={280} />
          ) : (
            <p className="muted">
              {actividades.length ? 'Sin actividades calificadas de este tipo en el corte.' : 'Sin actividades calificadas en este corte.'}
            </p>
          )}
        </div>
      </section>

      <div className="grid grid-3">
        <section className="card">
          <div className="card-head">
            <div className="card-titulo">
              <h2>Componentes</h2>
              <p>Exámenes 40 % · Tareas 30 % · APE 30 %</p>
            </div>
            <LeyendaReferencias />
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
            <p>Bajo la nota de aprobación</p>
          </div>
          <div className="card-body" style={{ paddingTop: 4 }}>
            {prioritarios.length === 0 && <p className="muted">Todos los estudiantes están aprobando.</p>}
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

      {notas.length > 0 && (
        <section className="card card-pad" aria-label="Hallazgos">
          <h2 style={{ marginBottom: 12 }}>{corte === 'periodo' ? 'Hallazgos del período' : `Hallazgos · ${etiquetaCorte}`}</h2>
          <div className="hallazgos-grid">
            <Hallazgo titulo="Rendimiento general" testid="hallazgo-rendimiento">
              <p>
                Promedio <b className="num">{r.promedio?.toFixed(2)}</b>/10 · Mediana <b className="num">{mediana(notas)?.toFixed(2)}</b>/10
              </p>
              <p>
                Aprobación <b className="num">{r.tasaAprobacion?.toFixed(1)} %</b>{' '}
                <span className="muted">({r.aprobados} de {r.evaluados} estudiantes)</span>
              </p>
            </Hallazgo>
            <Hallazgo titulo="Evolución por unidades" testid="hallazgo-unidades">
              {unidades.length >= 2 ? (
                <>
                  <p>
                    {nombreUnidad(unidades[0].unidad)} <b className="num">{unidades[0].promedio.toFixed(2)}</b> →{' '}
                    {nombreUnidad(unidades[unidades.length - 1].unidad)}{' '}
                    <b className="num">{unidades[unidades.length - 1].promedio.toFixed(2)}</b>
                  </p>
                  {(() => {
                    const d = unidades[unidades.length - 1].promedio - unidades[0].promedio;
                    return (
                      <p className={d < 0 ? 'variacion-baja' : d > 0 ? 'variacion-sube' : 'muted'}>
                        Variación <b className="num">{d >= 0 ? '+' : ''}{d.toFixed(2)}</b>{' '}
                        {d < 0 ? '(el grupo baja)' : d > 0 ? '(el grupo mejora)' : '(sin cambio)'}
                      </p>
                    );
                  })()}
                </>
              ) : (
                <p className="muted">Sólo hay notas de una unidad en este corte.</p>
              )}
            </Hallazgo>
            <Hallazgo titulo="Estudiantes que requieren atención" testid="hallazgo-atencion">
              {criticos.length === 0 && descenso.length === 0 && (
                <p className="muted">Ningún estudiante en nivel crítico ni con descenso sostenido.</p>
              )}
              {criticos.length > 0 && (
                <p>
                  <b>{plural(criticos.length, 'en nivel crítico', 'en nivel crítico')}</b>: {listaNombres(criticos)}
                </p>
              )}
              {descenso.length > 0 && (
                <p>
                  <b>{plural(descenso.length, 'con descenso sostenido', 'con descenso sostenido')}</b>: {listaNombres(descenso)}
                </p>
              )}
            </Hallazgo>
            <Hallazgo titulo="Componentes y pendientes" testid="hallazgo-componentes">
              {menorComponente && (
                <p>
                  Menor promedio: <b>{menorComponente.componente}</b> <b className="num">{menorComponente.promedio.toFixed(2)}</b>/10
                </p>
              )}
              <p>
                Nota 0: <b className="num">{estados.cero}</b> · Sin entrega: <b className="num">{estados.sin_entrega}</b>
              </p>
              <p className="muted">
                {plural(estados.pendiente, 'actividad pendiente de calificar', 'actividades pendientes de calificar')}
              </p>
            </Hallazgo>
          </div>
        </section>
      )}
    </>
  );
}
