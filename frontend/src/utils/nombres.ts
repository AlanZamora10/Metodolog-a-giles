/**
 * Nombres legibles para la interfaz (sin códigos técnicos).
 *   '(SOF) ESTRUCTURA DE DATOS - B'  ->  'Estructura de datos — Paralelo B'
 * Moodle guarda los nombres en mayúsculas y sin tildes: se restituyen las tildes conocidas.
 */

const TILDES: Record<string, string> = {
  programacion: 'programación',
  metodologias: 'metodologías',
  agiles: 'ágiles',
  configuracion: 'configuración',
  informatica: 'informática',
  ingenieria: 'ingeniería',
  analisis: 'análisis',
  logica: 'lógica',
  matematica: 'matemática',
  matematicas: 'matemáticas',
  estadistica: 'estadística',
  computacion: 'computación',
  tecnicas: 'técnicas',
};

function conTildes(texto: string): string {
  return texto
    .toLowerCase()
    .split(' ')
    .map((p) => TILDES[p] ?? p)
    .join(' ');
}

/** Materia y paralelo por separado. */
export function partesCurso(fullname: string): { materia: string; paralelo: string | null } {
  let nombre = (fullname || '').replace(/^\(\w+\)\s*/, '').trim();
  let paralelo: string | null = null;
  const m = nombre.match(/\s+-\s+([A-Z])$/);
  if (m) {
    paralelo = m[1];
    nombre = nombre.slice(0, m.index);
  }
  const materia = conTildes(nombre);
  return { materia: materia.charAt(0).toUpperCase() + materia.slice(1), paralelo };
}

/** 'Estructura de datos — Paralelo B' */
export function nombreCurso(fullname: string): string {
  const { materia, paralelo } = partesCurso(fullname);
  return paralelo ? `${materia} — Paralelo ${paralelo}` : materia;
}

/** 'Estructura de datos' (para frases como «¿Qué estudiantes de … necesitan atención?»). */
export function materiaCurso(fullname: string): string {
  return partesCurso(fullname).materia;
}
