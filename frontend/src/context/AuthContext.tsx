import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, expiracionToken, guardarSesion, leerSesion, registrarCierreSesion, type Sesion } from '../api/client';
import { endpoints } from '../api/endpoints';
import type { Usuario } from '../api/types';

interface AuthValor {
  usuario: Usuario | null;
  expira: number | null;
  /** Motivo del último cierre automático (token vencido / 401), para mostrarlo en el login. */
  aviso: string | null;
  iniciarSesion: (identificador: string, password: string) => Promise<void>;
  cerrarSesion: (aviso?: string) => void;
}

const AuthContext = createContext<AuthValor | null>(null);

/** Mensajes de RF-01 según el código HTTP del backend. */
export function mensajeErrorLogin(ex: unknown): string {
  if (ex instanceof ApiError) {
    if (ex.status === 401) return 'Credenciales inválidas. Verifique su correo/usuario y contraseña de Moodle UTA.';
    if (ex.status === 403)
      return ex.detail || 'Su cuenta de Moodle no tiene rol docente en ningún curso de Ingeniería de Software.';
    if (ex.status === 503) return 'Moodle UTA no responde en este momento. Intente nuevamente en unos minutos.';
    if (ex.status === 422) return 'Complete el usuario y la contraseña.';
    if (ex.status === 0) return ex.detail;
    return `Error inesperado (${ex.status}): ${ex.detail}`;
  }
  return 'No se pudo iniciar sesión.';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(() => leerSesion());
  const [aviso, setAviso] = useState<string | null>(null);

  const cerrarSesion = useCallback((motivo?: string) => {
    guardarSesion(null);
    try {
      sessionStorage.removeItem('edumonitor.chat');
      sessionStorage.removeItem('edumonitor.curso');
    } catch {
      /* sin almacenamiento */
    }
    setSesion(null);
    setAviso(motivo ?? null);
  }, []);

  const iniciarSesion = useCallback(async (identificador: string, password: string) => {
    const r = await endpoints.login(identificador.trim(), password);
    const nueva: Sesion = { token: r.access_token, usuario: r.user, expira: expiracionToken(r.access_token) };
    guardarSesion(nueva);
    setAviso(null);
    setSesion(nueva);
  }, []);

  // 401 desde cualquier petición -> cierre automático
  useEffect(() => {
    registrarCierreSesion(() => cerrarSesion('Su sesión expiró o ya no es válida. Inicie sesión nuevamente.'));
    return () => registrarCierreSesion(null);
  }, [cerrarSesion]);

  // Control de vencimiento: cierra la sesión justo cuando vence el JWT
  useEffect(() => {
    if (!sesion) return;
    const restante = sesion.expira - Date.now();
    if (restante <= 0) {
      cerrarSesion('Su sesión expiró. Inicie sesión nuevamente.');
      return;
    }
    const t = window.setTimeout(
      () => cerrarSesion('Su sesión expiró. Inicie sesión nuevamente.'),
      Math.min(restante, 2 ** 31 - 1),
    );
    return () => window.clearTimeout(t);
  }, [sesion, cerrarSesion]);

  const valor = useMemo<AuthValor>(
    () => ({ usuario: sesion?.usuario ?? null, expira: sesion?.expira ?? null, aviso, iniciarSesion, cerrarSesion }),
    [sesion, aviso, iniciarSesion, cerrarSesion],
  );
  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValor {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>');
  return ctx;
}
