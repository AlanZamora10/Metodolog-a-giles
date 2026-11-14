/**
 * Cliente HTTP del middleware.
 *  - Rutas relativas: en Docker Nginx reenvía /api al middleware; en desarrollo lo hace el proxy de Vite.
 *  - Adjunta el JWT (Bearer) guardado en sessionStorage.
 *  - Un 401 con sesión activa cierra la sesión (token vencido o revocado).
 */

import type { Usuario } from './types';

const CLAVE_SESION = 'edumonitor.sesion';

export interface Sesion {
  token: string;
  usuario: Usuario;
  /** Vencimiento del JWT (epoch en ms), leído del claim `exp`. */
  expira: number;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = 'ApiError';
  }
}

/** Lee el claim `exp` de un JWT (sin validar la firma: eso lo hace el backend). */
export function expiracionToken(token: string): number {
  try {
    const payload = token.split('.')[1];
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(payload.length / 4) * 4, '='));
    const exp = JSON.parse(json).exp;
    return typeof exp === 'number' ? exp * 1000 : 0;
  } catch {
    return 0;
  }
}

export function leerSesion(): Sesion | null {
  try {
    const raw = sessionStorage.getItem(CLAVE_SESION);
    if (!raw) return null;
    const sesion = JSON.parse(raw) as Sesion;
    if (!sesion.token || !sesion.expira || sesion.expira <= Date.now()) {
      sessionStorage.removeItem(CLAVE_SESION);
      return null;
    }
    return sesion;
  } catch {
    return null;
  }
}

export function guardarSesion(sesion: Sesion | null): void {
  try {
    if (sesion) sessionStorage.setItem(CLAVE_SESION, JSON.stringify(sesion));
    else sessionStorage.removeItem(CLAVE_SESION);
  } catch {
    /* almacenamiento no disponible: la sesión vive sólo en memoria */
  }
}

let alNoAutorizado: (() => void) | null = null;
export function registrarCierreSesion(fn: (() => void) | null): void {
  alNoAutorizado = fn;
}

async function extraerDetalle(resp: Response): Promise<string> {
  try {
    const data = await resp.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail)) return data.detail.map((d: { msg?: string }) => d.msg).join('; ');
  } catch {
    /* cuerpo no JSON */
  }
  return resp.statusText || `Error HTTP ${resp.status}`;
}

interface Opciones {
  method?: string;
  body?: unknown;
  /** Devuelve la Response cruda (descargas). */
  crudo?: boolean;
  signal?: AbortSignal;
}

export async function api<T>(ruta: string, opciones: Opciones = {}): Promise<T> {
  const sesion = leerSesion();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (opciones.body !== undefined) headers['Content-Type'] = 'application/json';
  if (sesion) headers.Authorization = `Bearer ${sesion.token}`;

  let resp: Response;
  try {
    resp = await fetch(ruta, {
      method: opciones.method ?? 'GET',
      headers,
      body: opciones.body !== undefined ? JSON.stringify(opciones.body) : undefined,
      signal: opciones.signal,
    });
  } catch (ex) {
    if ((ex as Error).name === 'AbortError') throw ex;
    throw new ApiError(0, 'No se pudo conectar con el servidor de EduMonitor.');
  }

  if (!resp.ok) {
    const detalle = await extraerDetalle(resp);
    if (resp.status === 401 && sesion) alNoAutorizado?.();
    throw new ApiError(resp.status, detalle);
  }
  if (opciones.crudo) return resp as unknown as T;
  return (await resp.json()) as T;
}
