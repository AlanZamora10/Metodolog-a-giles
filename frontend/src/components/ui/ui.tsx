import { useEffect, useRef, type ReactNode } from 'react';
import type { Actividad, EstadoAlerta } from '../../api/types';
import { ESTADOS_VISUALES, NIVELES, estadoVisual, type EstadoVisual } from '../../utils/academico';

export function KpiCard({ etiqueta, valor, unidad, detalle }: { etiqueta: string; valor: ReactNode; unidad?: string; detalle?: ReactNode }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{etiqueta}</span>
      <span className="kpi-value">
        {valor}
        {unidad && <small>{unidad}</small>}
      </span>
      {detalle && <span className="kpi-sub">{detalle}</span>}
    </div>
  );
}

export function NivelBadge({ nivel }: { nivel: string }) {
  const n = NIVELES[nivel];
  return <span className={`badge ${n?.clase ?? 'badge-neutral'}`}>{n?.etiqueta ?? nivel}</span>;
}

/** Estado visual de una actividad: icono + texto + color (nunca sólo color). */
export function EstadoActividadBadge({ estado }: { estado: EstadoVisual }) {
  const e = ESTADOS_VISUALES[estado];
  return (
    <span className="badge estado-badge" style={{ color: e.color }} data-estado={estado}>
      <span className="estado-icono" style={{ background: e.color }} aria-hidden>
        {e.icono}
      </span>
      {e.etiqueta}
    </span>
  );
}

export function EstadoDeActividad({ actividad }: { actividad: Pick<Actividad, 'estado' | 'nota'> }) {
  return <EstadoActividadBadge estado={estadoVisual(actividad)} />;
}

const ESTADO_ALERTA: Record<EstadoAlerta, { etiqueta: string; clase: string }> = {
  ABIERTA: { etiqueta: 'Abierta', clase: 'badge-info' },
  ATENDIDA: { etiqueta: 'En atención', clase: 'nivel-riesgo' },
  PUBLICADO: { etiqueta: 'Refuerzo publicado', clase: 'nivel-aceptable' },
  CERRADA: { etiqueta: 'Cerrada', clase: 'badge-neutral' },
  RESUELTA: { etiqueta: 'Resuelta', clase: 'badge-neutral' },
};

export function EstadoAlertaBadge({ estado }: { estado: EstadoAlerta }) {
  const e = ESTADO_ALERTA[estado] ?? { etiqueta: estado, clase: 'badge-neutral' };
  return <span className={`badge ${e.clase}`}>{e.etiqueta}</span>;
}

export function Aviso({ tipo, children }: { tipo: 'error' | 'warn' | 'ok' | 'info'; children: ReactNode }) {
  return (
    <div className={`alert-box ${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  );
}

export function Vacio({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{titulo}</strong>
      {children}
    </div>
  );
}

export function Spinner({ etiqueta }: { etiqueta?: string }) {
  return (
    <span role="status" style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
      <span className="spinner" aria-hidden />
      {etiqueta && <span>{etiqueta}</span>}
    </span>
  );
}

export function Esqueleto({ alto = 120 }: { alto?: number }) {
  return <div className="skeleton" style={{ height: alto }} aria-hidden />;
}

/** Diálogo de confirmación accesible (Escape cancela, foco inicial en "Cancelar"). */
export function Confirmacion({
  titulo,
  children,
  textoConfirmar,
  peligro,
  ocupado,
  onConfirmar,
  onCancelar,
}: {
  titulo: string;
  children: ReactNode;
  textoConfirmar: string;
  peligro?: boolean;
  ocupado?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}) {
  const cancelarRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelarRef.current?.focus();
    const tecla = (e: KeyboardEvent) => e.key === 'Escape' && !ocupado && onCancelar();
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onCancelar, ocupado]);
  return (
    <div className="modal-fondo" onClick={() => !ocupado && onCancelar()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-titulo" onClick={(e) => e.stopPropagation()}>
        <h2 id="modal-titulo">{titulo}</h2>
        <div>{children}</div>
        <div className="modal-acciones">
          <button ref={cancelarRef} className="btn" onClick={onCancelar} disabled={ocupado}>
            Cancelar
          </button>
          <button className={`btn ${peligro ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirmar} disabled={ocupado}>
            {ocupado && <span className="spinner" aria-hidden />}
            {textoConfirmar}
          </button>
        </div>
      </div>
    </div>
  );
}
