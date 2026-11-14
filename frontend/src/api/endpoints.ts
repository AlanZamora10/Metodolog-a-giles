import { api } from './client';
import type {
  Alerta,
  AtenderResponse,
  ChatResponse,
  CursoEstudiantes,
  EstadoSincronizacion,
  HerramientaCatalogo,
  PublicarRequest,
  PublicarResponse,
  Reporte,
  TokenResponse,
} from './types';

export const endpoints = {
  // RF-01
  login: (email: string, password: string) =>
    api<TokenResponse>('/api/v1/auth/login', { method: 'POST', body: { email, password } }),

  // RF-03 / RF-04 / RNF-08
  estadoSincronizacion: () => api<EstadoSincronizacion>('/api/sincronizacion'),
  sincronizar: () => api<EstadoSincronizacion>('/api/sincronizacion', { method: 'POST' }),
  estudiantesCurso: (courseId: number, signal?: AbortSignal) =>
    api<CursoEstudiantes>(`/api/cursos/${courseId}/estudiantes`, { signal }),

  // RF-07 / RF-10
  alertas: (courseId: number, signal?: AbortSignal) =>
    api<Alerta[]>(`/api/v1/alertas?course_id=${courseId}`, { signal }),
  atenderAlerta: (alertaId: number) =>
    api<AtenderResponse>(`/api/v1/alertas/${alertaId}/atender`, { method: 'POST' }),
  cerrarAlerta: (alertaId: number) =>
    api<{ status: string; mensaje: string; alerta: Alerta }>(`/api/v1/alertas/${alertaId}/cerrar`, { method: 'PATCH' }),
  publicarRefuerzo: (refuerzoId: number, body: PublicarRequest) =>
    api<PublicarResponse>(`/api/v1/refuerzos/${refuerzoId}/publicar`, { method: 'POST', body }),

  // RF-09 / RF-12
  chat: (mensaje: string, courseId?: number | null) =>
    api<ChatResponse>('/api/v1/agent/chat', { method: 'POST', body: { mensaje, course_id: courseId ?? null } }),
  herramientas: () => api<HerramientaCatalogo[]>('/api/v1/agent/herramientas'),

  // RF-11
  reporte: (courseId: number, signal?: AbortSignal) =>
    api<Reporte>(`/api/v1/courses/${courseId}/reporte`, { signal }),
  reporteMarkdown: (courseId: number) =>
    api<Response>(`/api/v1/courses/${courseId}/reporte?formato=md`, { crudo: true }),
};
