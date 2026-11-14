/**
 * Estado compartido del curso (RF-03 / RF-04 / RNF-08):
 *   - estado de sincronización con Moodle (fecha, origen, cursos del docente)
 *   - curso, período académico y corte (parcial) seleccionados
 *   - datos del curso: estudiantes con actividades, alertas e informe
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError } from '../api/client';
import { endpoints } from '../api/endpoints';
import type { Alerta, CursoEstudiantes, EstadoSincronizacion, Periodo, Reporte } from '../api/types';
import type { Corte } from '../utils/academico';

type EstadoSync = 'cargando' | 'listo' | 'sincronizando' | 'error';

interface CursoValor {
  sync: EstadoSincronizacion | null;
  estadoSync: EstadoSync;
  errorSync: string | null;
  sincronizar: () => Promise<void>;

  cursoId: number | null;
  seleccionarCurso: (id: number) => void;
  periodos: Periodo[];
  periodo: string | null;
  seleccionarPeriodo: (codigo: string) => void;
  corte: Corte;
  seleccionarCorte: (c: Corte) => void;

  datos: CursoEstudiantes | null;
  alertas: Alerta[];
  reporte: Reporte | null;
  cargandoCurso: boolean;
  errorCurso: string | null;
  recargarCurso: () => void;
  recargarAlertas: () => Promise<void>;
  actualizarAlerta: (a: Alerta) => void;
}

const CursoContext = createContext<CursoValor | null>(null);
const CLAVE = 'edumonitor.curso';

function leerPreferencia(): { cursoId?: number; corte?: Corte } {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE) ?? '{}');
  } catch {
    return {};
  }
}

function msg(ex: unknown): string {
  return ex instanceof ApiError ? ex.detail : 'Error de comunicación con el servidor.';
}

export function CursoProvider({ children }: { children: ReactNode }) {
  const pref = useRef(leerPreferencia());
  const [sync, setSync] = useState<EstadoSincronizacion | null>(null);
  const [estadoSync, setEstadoSync] = useState<EstadoSync>('cargando');
  const [errorSync, setErrorSync] = useState<string | null>(null);
  const [cursoId, setCursoId] = useState<number | null>(pref.current.cursoId ?? null);
  const [corte, setCorte] = useState<Corte>(pref.current.corte ?? 'periodo');
  const [periodo, setPeriodo] = useState<string | null>(null);

  const [datos, setDatos] = useState<CursoEstudiantes | null>(null);
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [reporte, setReporte] = useState<Reporte | null>(null);
  const [cargandoCurso, setCargandoCurso] = useState(false);
  const [errorCurso, setErrorCurso] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  const elegirCursoValido = useCallback((estado: EstadoSincronizacion) => {
    setCursoId((actual) =>
      actual && estado.cursos.some((c) => c.id === actual) ? actual : (estado.cursos[0]?.id ?? null),
    );
  }, []);

  // Estado inicial de sincronización (restaurado desde SQL Server tras reinicios)
  useEffect(() => {
    let vivo = true;
    endpoints
      .estadoSincronizacion()
      .then((s) => {
        if (!vivo) return;
        setSync(s);
        elegirCursoValido(s);
        setEstadoSync('listo');
      })
      .catch((ex) => {
        if (!vivo) return;
        setErrorSync(msg(ex));
        setEstadoSync('error');
      });
    return () => {
      vivo = false;
    };
  }, [elegirCursoValido]);

  const sincronizar = useCallback(async () => {
    setEstadoSync('sincronizando');
    setErrorSync(null);
    try {
      const s = await endpoints.sincronizar();
      setSync(s);
      elegirCursoValido(s);
      setEstadoSync('listo');
      setVersion((v) => v + 1);
    } catch (ex) {
      setErrorSync(
        ex instanceof ApiError && ex.status === 502 ? `Moodle UTA no respondió: ${ex.detail}` : msg(ex),
      );
      setEstadoSync('error');
    }
  }, [elegirCursoValido]);

  // Datos del curso seleccionado (estudiantes + alertas + informe en paralelo)
  useEffect(() => {
    if (!cursoId) {
      setDatos(null);
      setAlertas([]);
      setReporte(null);
      return;
    }
    const ctrl = new AbortController();
    setCargandoCurso(true);
    setErrorCurso(null);
    Promise.all([
      endpoints.estudiantesCurso(cursoId, ctrl.signal),
      endpoints.alertas(cursoId, ctrl.signal),
      endpoints.reporte(cursoId, ctrl.signal),
    ])
      .then(([est, al, rep]) => {
        setDatos(est);
        setAlertas(al);
        setReporte(rep);
        setPeriodo((p) => p ?? rep.periodo.codigo);
      })
      .catch((ex) => {
        if ((ex as Error).name === 'AbortError') return;
        setDatos(null);
        setAlertas([]);
        setReporte(null);
        setErrorCurso(msg(ex));
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setCargandoCurso(false);
      });
    return () => ctrl.abort();
  }, [cursoId, version]);

  useEffect(() => {
    try {
      sessionStorage.setItem(CLAVE, JSON.stringify({ cursoId, corte }));
    } catch {
      /* sin almacenamiento */
    }
  }, [cursoId, corte]);

  const recargarAlertas = useCallback(async () => {
    if (!cursoId) return;
    setAlertas(await endpoints.alertas(cursoId));
  }, [cursoId]);

  const actualizarAlerta = useCallback((a: Alerta) => {
    setAlertas((lista) => lista.map((x) => (x.id === a.id ? a : x)));
  }, []);

  // El backend expone el período vigente en el informe; se ofrece en el selector (RF-04).
  const periodos = useMemo(() => (reporte ? [reporte.periodo] : []), [reporte]);

  const valor: CursoValor = {
    sync,
    estadoSync,
    errorSync,
    sincronizar,
    cursoId,
    seleccionarCurso: setCursoId,
    periodos,
    periodo: periodo ?? periodos[0]?.codigo ?? null,
    seleccionarPeriodo: setPeriodo,
    corte,
    seleccionarCorte: setCorte,
    datos,
    alertas,
    reporte,
    cargandoCurso,
    errorCurso,
    recargarCurso: () => setVersion((v) => v + 1),
    recargarAlertas,
    actualizarAlerta,
  };
  return <CursoContext.Provider value={valor}>{children}</CursoContext.Provider>;
}

export function useCurso(): CursoValor {
  const ctx = useContext(CursoContext);
  if (!ctx) throw new Error('useCurso debe usarse dentro de <CursoProvider>');
  return ctx;
}
