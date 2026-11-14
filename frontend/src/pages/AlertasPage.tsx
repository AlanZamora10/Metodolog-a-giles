/**
 * RF-07 / RF-10: Centro de alertas e intervención.
 *  - Lista de alertas con evidencia numérica (sin etiquetas definitivas sobre el estudiante).
 *  - Al seleccionar/atender, el panel cambia AL INSTANTE al estudiante elegido; las respuestas
 *    tardías de una alerta anterior se descartan (contador de petición).
 *  - El docente edita la recomendación y aprueba explícitamente la publicación en Moodle (RN-17).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { endpoints } from '../api/endpoints';
import type { Alerta, PublicarResponse } from '../api/types';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { Aviso, Confirmacion, EstadoAlertaBadge, NivelBadge, Spinner, Vacio } from '../components/ui/ui';
import { REGLAS } from '../utils/academico';
import { fecha, fechaHora, fechaISOEnDias, nota } from '../utils/formato';

type Filtro = 'activas' | 'ABIERTA' | 'ATENDIDA' | 'PUBLICADO' | 'cerradas' | 'todas';
const FILTROS: { valor: Filtro; etiqueta: string }[] = [
  { valor: 'activas', etiqueta: 'Activas' },
  { valor: 'ABIERTA', etiqueta: 'Abiertas' },
  { valor: 'ATENDIDA', etiqueta: 'En atención' },
  { valor: 'PUBLICADO', etiqueta: 'Publicadas' },
  { valor: 'cerradas', etiqueta: 'Cerradas / resueltas' },
  { valor: 'todas', etiqueta: 'Todas' },
];
const ORDEN: Record<string, number> = { ABIERTA: 0, ATENDIDA: 1, PUBLICADO: 2, RESUELTA: 3, CERRADA: 4 };

function coincide(a: Alerta, f: Filtro): boolean {
  if (f === 'todas') return true;
  if (f === 'activas') return a.estado === 'ABIERTA' || a.estado === 'ATENDIDA' || a.estado === 'PUBLICADO';
  if (f === 'cerradas') return a.estado === 'CERRADA' || a.estado === 'RESUELTA';
  return a.estado === f;
}

export function AlertasPage() {
  return (
    <CursoRequerido>
      <CentroAlertas />
    </CursoRequerido>
  );
}

interface Borrador {
  alertaId: number;
  titulo: string;
  instrucciones: string;
  fechaEntrega: string;
}

function borradorInicial(a: Alerta): Borrador {
  return {
    alertaId: a.id,
    titulo: `Refuerzo: ${a.unidad_critica ?? 'unidad crítica'} — ${a.curso_codigo}`,
    instrucciones: a.diagnostico_ia ?? '',
    fechaEntrega: fechaISOEnDias(7),
  };
}

function CentroAlertas() {
  const { alertas, actualizarAlerta, recargarAlertas, datos } = useCurso();
  const [params, setParams] = useSearchParams();
  const [filtro, setFiltro] = useState<Filtro>('activas');
  const selId = Number(params.get('alerta')) || null;

  const [borrador, setBorrador] = useState<Borrador | null>(null);
  const [refuerzoId, setRefuerzoId] = useState<number | null>(null);
  const [origen, setOrigen] = useState<string | null>(null);
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publicaciones, setPublicaciones] = useState<Record<number, PublicarResponse>>({});
  const [confirmar, setConfirmar] = useState<'publicar' | 'cerrar' | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const peticion = useRef(0);

  const lista = useMemo(
    () =>
      alertas
        .filter((a) => coincide(a, filtro))
        .sort((a, b) => (ORDEN[a.estado] ?? 9) - (ORDEN[b.estado] ?? 9) || a.nota_promedio - b.nota_promedio),
    [alertas, filtro],
  );
  const sel = alertas.find((a) => a.id === selId) ?? null;

  /** Cambia el panel inmediatamente al estudiante de la alerta (sin esperar al backend). */
  const preparar = useCallback(
    (a: Alerta) => {
      peticion.current += 1; // invalida cualquier respuesta pendiente de otra alerta
      setParams({ alerta: String(a.id) }, { replace: true });
      setBorrador(borradorInicial(a));
      setRefuerzoId(a.refuerzo_id);
      setOrigen(null);
      setGenerando(false);
      setError(null);
      setConfirmar(null);
    },
    [setParams],
  );

  // Selección inicial por URL (?alerta=ID) o al cambiar de curso
  useEffect(() => {
    if (sel && borrador?.alertaId !== sel.id) preparar(sel);
    if (selId && !sel && alertas.length) setParams({}, { replace: true });
  }, [sel, selId, alertas.length, borrador, preparar, setParams]);

  const atender = useCallback(
    async (a: Alerta) => {
      preparar(a);
      const n = peticion.current;
      setGenerando(true);
      try {
        const r = await endpoints.atenderAlerta(a.id);
        if (n !== peticion.current) return; // respuesta tardía de otra alerta: se descarta
        actualizarAlerta(r.alerta);
        setRefuerzoId(r.refuerzo.id);
        setOrigen(r.refuerzo.origen);
        setBorrador((b) => ({
          alertaId: a.id,
          titulo: r.refuerzo.titulo,
          instrucciones: r.refuerzo.instrucciones ?? r.refuerzo.descripcion ?? '',
          fechaEntrega: b?.fechaEntrega ?? fechaISOEnDias(7),
        }));
      } catch (ex) {
        if (n !== peticion.current) return;
        setError(ex instanceof ApiError ? ex.detail : 'No se pudo generar el borrador.');
      } finally {
        if (n === peticion.current) setGenerando(false);
      }
    },
    [preparar, actualizarAlerta],
  );

  async function publicar() {
    if (!sel || !refuerzoId || !borrador) return;
    const n = peticion.current;
    setOcupado(true);
    setError(null);
    try {
      const r = await endpoints.publicarRefuerzo(refuerzoId, {
        confirmado: true,
        titulo: borrador.titulo.trim(),
        instrucciones: borrador.instrucciones.trim(),
        fecha_entrega: borrador.fechaEntrega,
      });
      setPublicaciones((p) => ({ ...p, [sel.id]: r }));
      actualizarAlerta({ ...sel, estado: 'PUBLICADO', refuerzo_id: r.refuerzo.id });
      recargarAlertas().catch(() => undefined);
    } catch (ex) {
      if (n === peticion.current) {
        setError(
          ex instanceof ApiError && ex.status === 502
            ? `Moodle UTA no creó la tarea (la alerta no cambió de estado): ${ex.detail}`
            : ex instanceof ApiError
              ? ex.detail
              : 'No se pudo publicar en Moodle.',
        );
      }
    } finally {
      setOcupado(false);
      setConfirmar(null);
    }
  }

  async function cerrar() {
    if (!sel) return;
    setOcupado(true);
    setError(null);
    try {
      const r = await endpoints.cerrarAlerta(sel.id);
      actualizarAlerta(r.alerta);
    } catch (ex) {
      setError(ex instanceof ApiError ? ex.detail : 'No se pudo cerrar la alerta.');
    } finally {
      setOcupado(false);
      setConfirmar(null);
    }
  }

  const publicado = sel ? publicaciones[sel.id] : undefined;
  const editable = !!sel && (sel.estado === 'ABIERTA' || sel.estado === 'ATENDIDA');
  const puedePublicar = editable && !!refuerzoId && !generando && !!borrador?.titulo.trim() && !!borrador?.instrucciones.trim();

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Centro de alertas</h1>
          <p>
            {datos!.shortname} · Alertas tempranas R1 (nota &lt; 5.00) y R2 (descenso sostenido) detectadas al sincronizar
          </p>
        </div>
        <div className="filtros" role="group" aria-label="Filtrar por estado">
          {FILTROS.map((f) => (
            <button
              key={f.valor}
              className={`btn btn-sm ${filtro === f.valor ? 'btn-primary' : ''}`}
              onClick={() => setFiltro(f.valor)}
              aria-pressed={filtro === f.valor}
            >
              {f.etiqueta} ({alertas.filter((a) => coincide(a, f.valor)).length})
            </button>
          ))}
        </div>
      </div>

      <div className="alertas-layout">
        <section className="card" aria-label="Listado de alertas">
          {lista.length === 0 && <Vacio titulo="No hay alertas en este filtro." />}
          {lista.map((a) => (
            <div
              key={a.id}
              className={`alerta-item ${a.id === selId ? 'sel' : ''}`}
              onClick={() => preparar(a)}
              role="button"
              tabIndex={0}
              aria-pressed={a.id === selId}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), preparar(a))}
              data-testid={`alerta-${a.id}`}
            >
              <div className="fila">
                <strong>{a.nombres}</strong>
                <span className="muted small">{a.id_number}</span>
                <span style={{ marginLeft: 'auto' }}>
                  <EstadoAlertaBadge estado={a.estado} />
                </span>
              </div>
              <div className="evidencia-num">
                <span>
                  Regla: <b>{REGLAS[a.regla] ?? a.regla}</b>
                </span>
                <span>
                  Nota ponderada: <b>{nota(a.nota_promedio)}</b>/10
                </span>
                {a.pendiente !== null && (
                  <span>
                    Pendiente: <b>{a.pendiente >= 0 ? '+' : ''}{a.pendiente.toFixed(2)}</b>
                  </span>
                )}
                {a.unidad_critica && (
                  <span>
                    Unidad más baja: <b>{a.unidad_critica}</b>
                  </span>
                )}
              </div>
              <div className="evidencia">{a.evidencia}</div>
              {(a.estado === 'ABIERTA' || a.estado === 'ATENDIDA') && (
                <div>
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={(e) => {
                      e.stopPropagation();
                      atender(a);
                    }}
                  >
                    {a.estado === 'ATENDIDA' ? 'Regenerar refuerzo' : 'Atender'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </section>

        <aside className="card panel-atencion" aria-label="Panel de atención" aria-live="polite">
          {!sel || !borrador || borrador.alertaId !== sel.id ? (
            <Vacio titulo="Seleccione una alerta">
              <p>El panel mostrará la evidencia del estudiante y el borrador de refuerzo para revisar y publicar.</p>
            </Vacio>
          ) : (
            <>
              <div className="card-head" style={{ alignItems: 'flex-start' }}>
                <div>
                  <h2 data-testid="panel-destinatario">{sel.nombres}</h2>
                  <p>
                    {sel.id_number} · {sel.email}
                  </p>
                </div>
                <EstadoAlertaBadge estado={sel.estado} />
              </div>
              <div className="card-body">
                <div className="evidencia-num" style={{ background: '#F8F9FA', borderRadius: 6, padding: '8px 10px' }}>
                  <span>
                    Nota ponderada <b>{nota(sel.nota_promedio)}</b>/10
                  </span>
                  <NivelBadge nivel={sel.nivel} />
                  {sel.tema_critico && (
                    <span>
                      Actividad más baja: <b>{sel.tema_critico}</b>
                    </span>
                  )}
                </div>
                <p className="small muted">
                  La alerta es una señal para revisión docente, no una calificación definitiva. Detectada {fechaHora(sel.fecha_creacion)}.{' '}
                  <Link to={`/estudiantes/${sel.id_number}`}>Ver ficha</Link>
                </p>

                {error && <Aviso tipo="error">{error}</Aviso>}

                {publicado ? (
                  <div className="publicado" data-testid="publicado">
                    <strong>✓ Tarea publicada en Moodle UTA</strong>
                    <span className="small">
                      Visible sólo para {sel.nombres}. Curso módulo (cmid): <b className="mono">{publicado.cmid}</b>
                    </span>
                    <span className="small">Fecha de entrega: {fechaHora(publicado.fecha_entrega)}</span>
                    <a href={publicado.moodle_link} target="_blank" rel="noreferrer" className="btn btn-sm" style={{ justifySelf: 'start', marginTop: 4 }}>
                      Abrir tarea en Moodle ↗
                    </a>
                  </div>
                ) : sel.estado === 'PUBLICADO' ? (
                  <Aviso tipo="ok">
                    <div>
                      <strong>Refuerzo #{sel.refuerzo_id} ya publicado en Moodle.</strong>
                      <div className="small">La tarea está en la sección «Refuerzos» del curso, visible sólo para el estudiante.</div>
                    </div>
                  </Aviso>
                ) : !editable ? (
                  <Aviso tipo="info">La alerta está {sel.estado.toLowerCase()}; no admite nuevas acciones.</Aviso>
                ) : (
                  <>
                    {generando && (
                      <Aviso tipo="info">
                        <Spinner etiqueta={`El agente está redactando el refuerzo para ${sel.nombres}…`} />
                      </Aviso>
                    )}
                    {!refuerzoId && !generando && (
                      <Aviso tipo="info">
                        <div>
                          Genere el borrador con el agente para poder publicarlo.{' '}
                          <button className="btn btn-sm btn-primary" onClick={() => atender(sel)} style={{ marginLeft: 6 }}>
                            Atender
                          </button>
                        </div>
                      </Aviso>
                    )}
                    {origen && <span className="badge badge-blue">Borrador generado por: {origen.toLowerCase().replace(/_/g, ' ')}</span>}
                    <label>
                      Destinatario
                      <input className="input" value={`${sel.nombres} <${sel.email}>`} readOnly aria-readonly />
                    </label>
                    <label>
                      Título de la tarea
                      <input
                        className="input"
                        maxLength={200}
                        value={borrador.titulo}
                        onChange={(e) => setBorrador({ ...borrador, titulo: e.target.value })}
                        disabled={generando}
                      />
                    </label>
                    <label>
                      Recomendación pedagógica / instrucciones
                      <textarea
                        className="textarea"
                        rows={7}
                        value={borrador.instrucciones}
                        onChange={(e) => setBorrador({ ...borrador, instrucciones: e.target.value })}
                        disabled={generando}
                        placeholder="Describa el refuerzo que realizará el estudiante…"
                      />
                    </label>
                    <label>
                      Fecha de entrega
                      <input
                        className="input"
                        type="date"
                        min={fechaISOEnDias(1)}
                        value={borrador.fechaEntrega}
                        onChange={(e) => setBorrador({ ...borrador, fechaEntrega: e.target.value })}
                        disabled={generando}
                      />
                    </label>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button className="btn btn-primary" onClick={() => setConfirmar('publicar')} disabled={!puedePublicar}>
                        Aprobar y publicar en Moodle
                      </button>
                      <button className="btn btn-danger" onClick={() => setConfirmar('cerrar')} disabled={generando}>
                        Cerrar alerta
                      </button>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </aside>
      </div>

      {confirmar === 'publicar' && sel && borrador && (
        <Confirmacion
          titulo="Publicar refuerzo en Moodle UTA"
          textoConfirmar="Aprobar y publicar"
          ocupado={ocupado}
          onConfirmar={publicar}
          onCancelar={() => setConfirmar(null)}
        >
          <p>
            Se creará la tarea <strong>«{borrador.titulo}»</strong> en la sección «Refuerzos» de {sel.curso_codigo}, visible{' '}
            <strong>sólo para {sel.nombres}</strong>, con entrega hasta el {fecha(borrador.fechaEntrega)} (23:59).
          </p>
        </Confirmacion>
      )}
      {confirmar === 'cerrar' && sel && (
        <Confirmacion
          titulo="Cerrar alerta"
          textoConfirmar="Cerrar alerta"
          peligro
          ocupado={ocupado}
          onConfirmar={cerrar}
          onCancelar={() => setConfirmar(null)}
        >
          <p>
            La alerta de <strong>{sel.nombres}</strong> pasará a CERRADA (estado terminal) y no se reabrirá.
          </p>
        </Confirmacion>
      )}
    </>
  );
}
