/**
 * Tipos que reflejan exactamente las respuestas del middleware FastAPI (verificadas contra la API real).
 * Rutas: middleware/app/routers/{auth,sincronizacion,courses,alerts,agente}.py
 */

// ---------- Autenticación (POST /api/v1/auth/login) ----------
export interface Usuario {
  id: number;
  nombres: string;
  email: string;
  rol: string;
  id_number: string | null;
  activo: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: Usuario;
}

// ---------- Sincronización (GET/POST /api/sincronizacion) ----------
export interface CursoResumen {
  id: number;
  shortname: string;
  fullname: string;
  total_estudiantes: number;
  promedio: number;
  criticos: number;
  en_riesgo: number;
  aceptables: number;
  alertas_r1: number;
  alertas_r2: number;
}

export interface EstadoSincronizacion {
  ultima_sincronizacion: string | null;
  moodle: { sitio?: string; version?: string } | null;
  persistencia: { motor?: string; origen?: string; alertas?: unknown; error?: string } | null;
  total_cursos: number;
  total_estudiantes: number;
  cursos: CursoResumen[];
  estudiantes: { id_number: string; nombres: string; email: string }[];
  // Sólo en la respuesta del POST
  status?: string;
  duracion_ms?: number;
  log_id?: number;
}

// ---------- Estudiantes de un curso (GET /api/cursos/{id}/estudiantes) ----------
export type EstadoActividadMoodle = 'CALIFICADO' | 'SIN_ENTREGA' | 'PENDIENTE';
export type Componente = 'ACD' | 'TAREAS' | 'PAE';
export type NivelRiesgo = 'CRITICO' | 'EN_RIESGO' | 'ACEPTABLE';

export interface Actividad {
  id_number: string;
  nombre: string | null;
  componente: Componente;
  unidad: number;
  parcial: number;
  nota: number | null;
  estado: EstadoActividadMoodle;
}

export interface MetricasEstudiante {
  acd: number | null;
  tareas: number | null;
  pae: number | null;
  nota_final: number;
  nivel_riesgo: NivelRiesgo;
  promedios_unidad: Record<string, number | null>;
  pendiente: number;
  tendencia: string;
  probabilidad_aprobacion: number;
}

export interface Estudiante extends MetricasEstudiante {
  moodle_id: number;
  id_number: string;
  nombres: string;
  email: string;
  estados: Partial<Record<Componente, EstadoActividadMoodle>>;
  actividades: Actividad[];
  regla_alerta: string | null;
  parcial_vigente: number;
  por_parcial: Record<string, MetricasEstudiante>;
}

export interface CursoEstudiantes extends CursoResumen {
  estudiantes: Estudiante[];
}

// ---------- Alertas y refuerzos (/api/v1/alertas, /api/v1/refuerzos) ----------
export type EstadoAlerta = 'ABIERTA' | 'ATENDIDA' | 'PUBLICADO' | 'CERRADA' | 'RESUELTA';

export interface Alerta {
  id: number;
  curso_id: number | null;
  curso_codigo: string;
  curso_nombre: string;
  id_number: string;
  nombres: string;
  email: string;
  regla: string;
  nivel: string;
  nota_promedio: number;
  pendiente: number | null;
  evidencia: string;
  unidad_critica: string | null;
  tema_critico: string | null;
  estado: EstadoAlerta;
  diagnostico_ia: string | null;
  tipo_accion_sugerida: string | null;
  fecha_creacion: string | null;
  fecha_actualizacion: string | null;
  refuerzo_id: number | null;
}

export interface Refuerzo {
  id: number;
  alerta_id: number;
  titulo: string;
  descripcion: string | null;
  instrucciones: string | null;
  actividades: string[] | null;
  origen: string | null;
  estado: string;
  cmid: number | null;
  moodle_url: string | null;
  fecha_entrega?: string | null;
  fecha_publicacion?: string | null;
}

export interface AtenderResponse {
  status: string;
  mensaje: string;
  alerta: Alerta;
  refuerzo: Refuerzo;
  diagnostico: Record<string, unknown>;
}

export interface PublicarRequest {
  confirmado: boolean;
  titulo?: string;
  instrucciones?: string;
  fecha_entrega?: string; // AAAA-MM-DD
}

export interface PublicarResponse {
  status: string;
  mensaje: string;
  cmid: number;
  moodle_link: string;
  fecha_entrega: string;
  refuerzo: Refuerzo;
}

// ---------- Agente (POST /api/v1/agent/chat) ----------
export interface HerramientaUsada {
  herramienta: string;
  parametros: Record<string, unknown>;
  resultado: Record<string, unknown> & { filas?: number; error?: string };
}

export interface ChatResponse {
  respuesta: string;
  herramientas: HerramientaUsada[];
  plan_fuente: string;
  redaccion: string;
  duracion_ms: number;
}

export interface HerramientaCatalogo {
  nombre: string;
  descripcion: string;
  parametros: Record<string, string>;
}

// ---------- Informe (GET /api/v1/courses/{id}/reporte) ----------
export interface Periodo {
  codigo: string;
  nombre: string;
  inicio: string;
  fin: string;
}

export interface Reporte {
  curso: { id: number; shortname: string; fullname: string; docentes: string[] };
  periodo: Periodo;
  fecha_sincronizacion: string | null;
  generado_en: string;
  metricas: {
    total_estudiantes: number;
    promedio: number;
    mediana: number;
    nota_minima: number;
    nota_maxima: number;
    desviacion_estandar: number;
    criticos: number;
    en_riesgo: number;
    aceptables: number;
    porcentaje_aceptables: number;
    componentes: { acd: number | null; tareas: number | null; pae: number | null };
    promedio_por_unidad: Record<string, number | null>;
  };
  distribucion_estados: {
    calificado: number;
    cero: number;
    sin_entrega: number;
    pendiente: number;
    total_registros: number;
    estudiantes_con_cero: number;
    estudiantes_sin_entrega: number;
    estudiantes_con_pendiente: number;
  };
  alertas: {
    r1_activas: number;
    r2_activas: number;
    abiertas: number;
    atendidas: number;
    publicadas: number;
    cerradas: number;
    resueltas: number;
  };
  estudiantes_prioritarios: {
    id_number: string;
    nombres: string;
    nota_final: number;
    nivel_riesgo: string;
    regla_alerta: string | null;
  }[];
  hallazgos: string[];
  recomendaciones: string[];
}
