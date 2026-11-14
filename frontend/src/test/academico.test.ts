import { describe, expect, it } from 'vitest';
import { contarEstados, estadoVisual, histograma, metricasEnCorte, resumenGrupo } from '../utils/academico';
import { expiracionToken, guardarSesion, leerSesion } from '../api/client';
import { DOCENTE, ESTUDIANTES, tokenFalso } from './helpers';

describe('RF-06 · estados de actividad', () => {
  it('distingue calificada, nota cero, sin entrega y pendiente (misma regla que el informe del backend)', () => {
    expect(estadoVisual({ estado: 'CALIFICADO', nota: 7.5 })).toBe('calificada');
    expect(estadoVisual({ estado: 'CALIFICADO', nota: 0 })).toBe('cero');
    expect(estadoVisual({ estado: 'SIN_ENTREGA', nota: 0 })).toBe('sin_entrega');
    expect(estadoVisual({ estado: 'PENDIENTE', nota: null })).toBe('pendiente');
  });

  it('cuenta los cuatro estados de un estudiante', () => {
    expect(contarEstados(ESTUDIANTES.estudiantes[0].actividades)).toEqual({ calificada: 1, cero: 1, sin_entrega: 1, pendiente: 1 });
  });
});

describe('RF-05 · KPIs del grupo', () => {
  it('promedio /10, tasa de aprobación (≥ 7.00) y niveles', () => {
    const r = resumenGrupo(ESTUDIANTES.estudiantes, 'periodo');
    expect(r.total).toBe(3);
    expect(r.promedio).toBe(6.05);
    expect(r.aprobados).toBe(1);
    expect(r.tasaAprobacion).toBe(33.3);
    expect(r.niveles).toEqual({ CRITICO: 1, EN_RIESGO: 1, ACEPTABLE: 1 });
  });

  it('el corte por parcial usa por_parcial y excluye a quien no tiene notas en ese parcial', () => {
    expect(metricasEnCorte(ESTUDIANTES.estudiantes[0], '1')?.nota_final).toBe(3.04);
    expect(metricasEnCorte(ESTUDIANTES.estudiantes[0], '2')).toBeNull();
    expect(resumenGrupo(ESTUDIANTES.estudiantes, '2').evaluados).toBe(0);
  });

  it('histograma en tramos de 2 puntos (10.0 cae en 8–10)', () => {
    expect(histograma([0, 3.04, 6.2, 8.9, 10]).map((t) => t.estudiantes)).toEqual([1, 1, 0, 1, 2]);
  });
});

describe('RF-01 · sesión JWT en sessionStorage', () => {
  it('lee el vencimiento del claim exp', () => {
    const exp = expiracionToken(tokenFalso(30));
    expect(exp).toBeGreaterThan(Date.now() + 29 * 60_000);
  });

  it('descarta una sesión vencida', () => {
    guardarSesion({ token: 'x', usuario: DOCENTE, expira: Date.now() - 1000 });
    expect(leerSesion()).toBeNull();
    expect(sessionStorage.getItem('edumonitor.sesion')).toBeNull();
  });
});
