import { describe, expect, it } from 'vitest';
import { materiaCurso, nombreCurso } from '../utils/nombres';

describe('Nombres legibles de los cursos de ambos docentes', () => {
  it('restituye tildes y conserva los numerales romanos de las materias seriadas', () => {
    expect(nombreCurso('(SOF) INGENIERIA DE SOFTWARE I - A')).toBe('Ingeniería de software I — Paralelo A');
    expect(nombreCurso('(SOF) BASES DE DATOS AVANZADAS - B')).toBe('Bases de datos avanzadas — Paralelo B');
    expect(materiaCurso('(SOF) DESARROLLO WEB - A')).toBe('Desarrollo web');
    expect(nombreCurso('(SOF) METODOLOGIAS AGILES - B')).toBe('Metodologías ágiles — Paralelo B');
  });
});
