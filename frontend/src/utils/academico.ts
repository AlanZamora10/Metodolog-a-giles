/**
 * Reglas de presentación académica (mismas que middleware/app/services/reporte_service.py):
 *   SIN_ENTREGA -> "sin entrega" | PENDIENTE -> "pendiente de calificación"
 *   CALIFICADO con nota 0 -> "nota cero (0.0)" | resto -> "calificada"
 */

import type { Actividad, Estudiante, MetricasEstudiante } from '../api/types';

export type EstadoVisual = 'calificada' | 'cero' | 'sin_entrega' | 'pendiente';

export const ESTADOS_VISUALES: Record<EstadoVisual, { etiqueta: string; icono: string; color: string }> = {
  calificada: { etiqueta: 'Calificada', icono: '✓', color: 'var(--estado-calificada)' },
  cero: { etiqueta: 'Nota cero (0.0)', icono: '0', color: 'var(--estado-cero)' },
  sin_entrega: { etiqueta: 'Sin entrega', icono: '✕', color: 'var(--estado-sin-entrega)' },
  pendiente: { etiqueta: 'Pendiente de calificación', icono: '…', color: 'var(--estado-pendiente)' },
};

export const ORDEN_ESTADOS: EstadoVisual[] = ['calificada', 'cero', 'sin_entrega', 'pendiente'];

export function estadoVisual(a: Pick<Actividad, 'estado' | 'nota'>): EstadoVisual {
  if (a.estado === 'SIN_ENTREGA') return 'sin_entrega';
  if (a.estado === 'PENDIENTE') return 'pendiente';
  if (a.nota === 0) return 'cero';
  return 'calificada';
}

export function contarEstados(actividades: Actividad[]): Record<EstadoVisual, number> {
  const conteo: Record<EstadoVisual, number> = { calificada: 0, cero: 0, sin_entrega: 0, pendiente: 0 };
  for (const a of actividades) conteo[estadoVisual(a)] += 1;
  return conteo;
}

/** Corte de evaluación dentro del período: todo el período, o un parcial (1 / 2). */
export type Corte = 'periodo' | '1' | '2';

export const CORTES: { valor: Corte; etiqueta: string }[] = [
  { valor: 'periodo', etiqueta: 'Período completo' },
  { valor: '1', etiqueta: 'Primer parcial (U1–U2)' },
  { valor: '2', etiqueta: 'Segundo parcial (U3–U4)' },
];

/** Métricas del estudiante para el corte elegido; null si no tiene evaluaciones en ese parcial. */
export function metricasEnCorte(e: Estudiante, corte: Corte): MetricasEstudiante | null {
  if (corte === 'periodo') return e;
  return e.por_parcial?.[corte] ?? null;
}

export function actividadesEnCorte(e: Estudiante, corte: Corte): Actividad[] {
  return corte === 'periodo' ? e.actividades : e.actividades.filter((a) => String(a.parcial) === corte);
}

export const UMBRAL_CRITICO = 5;
export const UMBRAL_APROBACION = 7;

export const NIVELES: Record<string, { etiqueta: string; clase: string }> = {
  CRITICO: { etiqueta: 'Crítico (< 5.00)', clase: 'nivel-critico' },
  EN_RIESGO: { etiqueta: 'En riesgo (5.00–6.99)', clase: 'nivel-riesgo' },
  ACEPTABLE: { etiqueta: 'Aceptable (≥ 7.00)', clase: 'nivel-aceptable' },
};

export const REGLAS: Record<string, string> = {
  R1_NOTA_CRITICA: 'R1 · nota ponderada < 5.00',
  R2_DESCENSO: 'R2 · descenso sostenido entre unidades',
};

export function nivelPorNota(nota: number): 'CRITICO' | 'EN_RIESGO' | 'ACEPTABLE' {
  if (nota < UMBRAL_CRITICO) return 'CRITICO';
  if (nota < UMBRAL_APROBACION) return 'EN_RIESGO';
  return 'ACEPTABLE';
}

export interface ResumenGrupo {
  total: number;
  evaluados: number;
  promedio: number | null;
  aprobados: number;
  tasaAprobacion: number | null;
  niveles: Record<'CRITICO' | 'EN_RIESGO' | 'ACEPTABLE', number>;
}

/** KPIs del grupo para el corte elegido (para "período completo" coincide con el informe del backend). */
export function resumenGrupo(estudiantes: Estudiante[], corte: Corte): ResumenGrupo {
  const metricas = estudiantes.map((e) => metricasEnCorte(e, corte)).filter((m): m is MetricasEstudiante => !!m);
  const notas = metricas.map((m) => m.nota_final);
  const aprobados = notas.filter((n) => n >= UMBRAL_APROBACION).length;
  const niveles = { CRITICO: 0, EN_RIESGO: 0, ACEPTABLE: 0 };
  for (const n of notas) niveles[nivelPorNota(n)] += 1;
  return {
    total: estudiantes.length,
    evaluados: notas.length,
    promedio: notas.length ? redondear(notas.reduce((s, n) => s + n, 0) / notas.length) : null,
    aprobados,
    tasaAprobacion: notas.length ? redondear((aprobados * 100) / notas.length, 1) : null,
    niveles,
  };
}

/** Histograma de notas finales en tramos de 2 puntos (0–2, 2–4, …, 8–10). */
export function histograma(notas: number[]): { tramo: string; estudiantes: number; desde: number }[] {
  const tramos = [0, 2, 4, 6, 8].map((desde) => ({ tramo: `${desde}–${desde + 2}`, estudiantes: 0, desde }));
  for (const n of notas) tramos[Math.min(4, Math.max(0, Math.floor(n / 2)))].estudiantes += 1;
  return tramos;
}

/** Promedio del grupo por unidad (U1..U4) en el corte. */
export function promedioPorUnidad(estudiantes: Estudiante[], corte: Corte): { unidad: string; promedio: number }[] {
  const acum: Record<string, number[]> = {};
  for (const e of estudiantes) {
    const m = metricasEnCorte(e, corte);
    if (!m) continue;
    for (const [u, v] of Object.entries(m.promedios_unidad ?? {})) {
      if (v !== null && v !== undefined) (acum[u] ??= []).push(v);
    }
  }
  return Object.keys(acum)
    .sort()
    .map((u) => ({ unidad: u, promedio: redondear(acum[u].reduce((s, n) => s + n, 0) / acum[u].length) }));
}

/** Promedio del grupo por actividad (calificaciones que cuentan) en el corte. */
export function promedioPorActividad(estudiantes: Estudiante[], corte: Corte): { actividad: string; nombre: string; promedio: number }[] {
  const acum: Record<string, { nombre: string; notas: number[] }> = {};
  for (const e of estudiantes) {
    for (const a of actividadesEnCorte(e, corte)) {
      if (a.nota === null) continue;
      (acum[a.id_number] ??= { nombre: a.nombre ?? a.id_number, notas: [] }).notas.push(a.nota);
    }
  }
  return Object.keys(acum)
    .sort()
    .map((k) => ({
      actividad: k,
      nombre: acum[k].nombre,
      promedio: redondear(acum[k].notas.reduce((s, n) => s + n, 0) / acum[k].notas.length),
    }));
}

/** Promedio del grupo por componente (ACD 40 %, Tareas 30 %, PAE 30 %) en el corte. */
export function promedioPorComponente(estudiantes: Estudiante[], corte: Corte) {
  const comp = { acd: [] as number[], tareas: [] as number[], pae: [] as number[] };
  for (const e of estudiantes) {
    const m = metricasEnCorte(e, corte);
    if (!m) continue;
    if (m.acd !== null) comp.acd.push(m.acd);
    if (m.tareas !== null) comp.tareas.push(m.tareas);
    if (m.pae !== null) comp.pae.push(m.pae);
  }
  const prom = (v: number[]) => (v.length ? redondear(v.reduce((s, n) => s + n, 0) / v.length) : 0);
  return [
    { componente: 'ACD (40 %)', promedio: prom(comp.acd) },
    { componente: 'Tareas (30 %)', promedio: prom(comp.tareas) },
    { componente: 'PAE (30 %)', promedio: prom(comp.pae) },
  ];
}

export function redondear(n: number, decimales = 2): number {
  const f = 10 ** decimales;
  return Math.round(n * f) / f;
}
