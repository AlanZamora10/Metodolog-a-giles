import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { AuthProvider } from '../context/AuthContext';
import { AppRoutes } from '../App';
import { guardarSesion } from '../api/client';
import type { Alerta, CursoEstudiantes, EstadoSincronizacion, Estudiante, Reporte, Usuario } from '../api/types';

export const DOCENTE: Usuario = {
  id: 1,
  nombres: 'Ing. Roberto Gómez',
  email: 'rgomez@uta.edu.ec',
  rol: 'DOCENTE',
  id_number: 'U-01',
  activo: true,
};

/** JWT sin firma válida (el frontend sólo lee `exp`). */
export function tokenFalso(minutos = 60): string {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ sub: DOCENTE.email, exp: Math.floor(Date.now() / 1000) + minutos * 60 })}.firma`;
}

export function iniciarSesionFalsa(minutos = 60) {
  const token = tokenFalso(minutos);
  guardarSesion({ token, usuario: DOCENTE, expira: Date.now() + minutos * 60_000 });
  return token;
}

export const SYNC: EstadoSincronizacion = {
  ultima_sincronizacion: '2026-11-14T02:51:25.483004+00:00',
  moodle: { sitio: 'Moodle UTA', version: '4.3.2 (Build: 20231222)' },
  persistencia: { motor: 'mssql', origen: 'restaurado_desde_bd' },
  total_cursos: 1,
  total_estudiantes: 3,
  cursos: [
    { id: 2, shortname: 'SOF-POO-A', fullname: '(SOF) PROGRAMACION ORIENTADA A OBJETOS - A', total_estudiantes: 3, promedio: 5.64, criticos: 1, en_riesgo: 1, aceptables: 1, alertas_r1: 1, alertas_r2: 0 },
  ],
  estudiantes: [],
};

function est(id: string, nombres: string, nota_final: number, nivel: Estudiante['nivel_riesgo'], actividades: Estudiante['actividades'], regla: string | null = null): Estudiante {
  const m = { acd: nota_final, tareas: nota_final, pae: nota_final, nota_final, nivel_riesgo: nivel, promedios_unidad: { U1: nota_final, U2: nota_final }, pendiente: -0.1, tendencia: 'ESTABLE', probabilidad_aprobacion: 50 };
  return {
    ...m,
    moodle_id: 100,
    id_number: id,
    nombres,
    email: `${id.toLowerCase()}@uta.edu.ec`,
    estados: {},
    actividades,
    regla_alerta: regla,
    parcial_vigente: 1,
    por_parcial: { '1': m },
  };
}

export const ESTUDIANTES: CursoEstudiantes = {
  ...SYNC.cursos[0],
  estudiantes: [
    est('U-04', 'Diego Curillo', 3.04, 'CRITICO', [
      { id_number: 'U1-A1', nombre: 'Evaluación Unidad 1', componente: 'ACD', unidad: 1, parcial: 1, nota: 6.0, estado: 'CALIFICADO' },
      { id_number: 'U1-T2', nombre: 'Tarea 2', componente: 'TAREAS', unidad: 1, parcial: 1, nota: 0, estado: 'CALIFICADO' },
      { id_number: 'U2-T4', nombre: 'Tarea 4', componente: 'TAREAS', unidad: 2, parcial: 1, nota: 0, estado: 'SIN_ENTREGA' },
      { id_number: 'U2-P1', nombre: 'Proyecto', componente: 'PAE', unidad: 2, parcial: 1, nota: null, estado: 'PENDIENTE' },
    ], 'R1_NOTA_CRITICA'),
    est('U-05', 'Valeria Ortiz', 6.2, 'EN_RIESGO', [
      { id_number: 'U1-A1', nombre: 'Evaluación Unidad 1', componente: 'ACD', unidad: 1, parcial: 1, nota: 6.2, estado: 'CALIFICADO' },
    ]),
    est('U-06', 'Camila Andrade', 8.9, 'ACEPTABLE', [
      { id_number: 'U1-A1', nombre: 'Evaluación Unidad 1', componente: 'ACD', unidad: 1, parcial: 1, nota: 8.9, estado: 'CALIFICADO' },
    ]),
  ],
};

function alerta(id: number, id_number: string, nombres: string, nota: number): Alerta {
  return {
    id, curso_id: 2, curso_codigo: 'SOF-POO-A', curso_nombre: 'POO', id_number, nombres,
    email: `${id_number.toLowerCase()}@uta.edu.ec`, regla: 'R1_NOTA_CRITICA', nivel: 'CRITICO', nota_promedio: nota,
    pendiente: -0.25, evidencia: `R1: nota ponderada ${nota}/10 (< 5.00).`, unidad_critica: 'Unidad 2',
    tema_critico: 'U1-T2 - Tarea 2', estado: 'ABIERTA', diagnostico_ia: null, tipo_accion_sugerida: null,
    fecha_creacion: '2026-11-14T02:48:55+00:00', fecha_actualizacion: null, refuerzo_id: null,
  };
}

export const ALERTAS: Alerta[] = [alerta(1, 'U-04', 'Diego Curillo', 3.04), alerta(2, 'U-07', 'Valeria Ortiz', 4.07)];

export const REPORTE: Reporte = {
  curso: { id: 2, shortname: 'SOF-POO-A', fullname: '(SOF) PROGRAMACION ORIENTADA A OBJETOS - A', docentes: ['rgomez@uta.edu.ec'] },
  periodo: { codigo: '2026-JD', nombre: 'Julio a Diciembre 2026', inicio: '2026-07-01', fin: '2026-12-31' },
  fecha_sincronizacion: SYNC.ultima_sincronizacion,
  generado_en: '2026-11-14T03:00:00+00:00',
  metricas: {
    total_estudiantes: 3, promedio: 6.05, mediana: 6.2, nota_minima: 3.04, nota_maxima: 8.9, desviacion_estandar: 2.4,
    criticos: 1, en_riesgo: 1, aceptables: 1, porcentaje_aceptables: 33.3,
    componentes: { acd: 7.03, tareas: 6.38, pae: 6.7 }, promedio_por_unidad: { U1: 6.68, U2: 6.45 },
  },
  distribucion_estados: { calificado: 4, cero: 1, sin_entrega: 1, pendiente: 1, total_registros: 7, estudiantes_con_cero: 1, estudiantes_sin_entrega: 1, estudiantes_con_pendiente: 1 },
  alertas: { r1_activas: 2, r2_activas: 0, abiertas: 2, atendidas: 0, publicadas: 0, cerradas: 0, resueltas: 0 },
  estudiantes_prioritarios: [{ id_number: 'U-04', nombres: 'Diego Curillo', nota_final: 3.04, nivel_riesgo: 'CRITICO', regla_alerta: 'R1_NOTA_CRITICA' }],
  hallazgos: ['Promedio del curso 6.05/10 (mediana 6.20).'],
  recomendaciones: ['Atender primero las alertas R1.'],
};

export const json = (cuerpo: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json', ...headers } });

type Manejador = (init: RequestInit | undefined, url: string) => Response | Promise<Response>;

/**
 * Sustituye fetch: cada clave es "MÉTODO /ruta" (sin query) y su respuesta.
 * Rutas del curso ya registradas por defecto; se pueden sobrescribir.
 */
export function mockApi(rutas: Record<string, Manejador> = {}) {
  const base: Record<string, Manejador> = {
    'GET /api/sincronizacion': () => json(SYNC),
    'GET /api/cursos/2/estudiantes': () => json(ESTUDIANTES),
    'GET /api/v1/alertas': () => json(ALERTAS),
    'GET /api/v1/courses/2/reporte': () => json(REPORTE),
    'GET /api/v1/agent/herramientas': () =>
      json([
        { nombre: 'listar_cursos_autorizados', descripcion: 'Lista cursos', parametros: {} },
        { nombre: 'obtener_calificaciones', descripcion: 'Notas', parametros: {} },
      ]),
    ...rutas,
  };
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const clave = `${init?.method ?? 'GET'} ${url.split('?')[0]}`;
    const h = base[clave];
    if (!h) return json({ detail: `ruta no simulada: ${clave}` }, 404);
    return h(init, url);
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

export function renderApp(ruta: string) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

/** Promesa controlable para simular respuestas lentas o fuera de orden. */
export function diferido<T>() {
  let resolver!: (v: T) => void;
  const promesa = new Promise<T>((r) => (resolver = r));
  return { promesa, resolver };
}
