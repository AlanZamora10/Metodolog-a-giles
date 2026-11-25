/**
 * Centro de alertas e intervención.
 *  - Lista de alertas con evidencia numérica (sin etiquetas definitivas sobre el estudiante).
 *  - Al seleccionar/atender, el panel cambia AL INSTANTE al estudiante elegido; las respuestas
 *    tardías de una alerta anterior se descartan (contador de petición).
 *  - El docente edita la recomendación y aprueba explícitamente la publicación en Moodle (RN-17).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { endpoints } from '../api/endpoints';
import type { Alerta, PublicarResponse } from '../api/types';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { Aviso, Confirmacion, EstadoAlertaBadge, NivelBadge, Spinner, Vacio } from '../components/ui/ui';
import { REGLAS } from '../utils/academico';
import { fecha, fechaHora, fechaISOEnDias, nota } from '../utils/formato';
import { nombreCurso } from '../utils/nombres';

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

type FiltroParcial = 'todos' | 1 | 2;
const FILTROS_PARCIAL: { valor: FiltroParcial; etiqueta: string }[] = [
  { valor: 'todos', etiqueta: 'Ambos parciales' },
  { valor: 1, etiqueta: 'Primer Parcial' },
  { valor: 2, etiqueta: 'Segundo Parcial' },
];
const NOMBRE_PARCIAL: Record<number, string> = { 1: 'Primer Parcial', 2: 'Segundo Parcial' };

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
  /** Texto preparado por el agente IA desde el chat (proponer_refuerzo): se conserva al registrar la atención. */
  desdeAgente?: boolean;
}

/** Propuesta enviada desde el chat del agente ("Aplicar en el Centro de alertas"). */
interface PropuestaAgente {
  alertaId: number;
  titulo: string;
  instrucciones: string;
}

function borradorInicial(a: Alerta, propuesta?: PropuestaAgente | null): Borrador {
  if (propuesta && propuesta.alertaId === a.id) {
    return { alertaId: a.id, titulo: propuesta.titulo, instrucciones: propuesta.instrucciones, fechaEntrega: fechaISOEnDias(7), desdeAgente: true };
  }
  return {
    alertaId: a.id,
    titulo: `Refuerzo: ${a.unidad_critica ?? 'unidad crítica'} — ${a.curso_codigo}`,
    instrucciones: a.diagnostico_ia ?? '',
    fechaEntrega: fechaISOEnDias(7),
  };
}

function CentroAlertas() {
  const { alertas, actualizarAlerta, recargarAlertas, datos, cursoId } = useCurso();
  const [params, setParams] = useSearchParams();
  const propuesta = (useLocation().state as { propuesta?: PropuestaAgente } | null)?.propuesta ?? null;
  const [filtro, setFiltro] = useState<Filtro>('activas');
  const [parcial, setParcial] = useState<FiltroParcial>('todos');
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
        .filter((a) => coincide(a, filtro) && (parcial === 'todos' || a.parcial === parcial))
        .sort((a, b) => (ORDEN[a.estado] ?? 9) - (ORDEN[b.estado] ?? 9) || a.nota_promedio - b.nota_promedio),
    [alertas, filtro, parcial],
  );
  const sel = alertas.find((a) => a.id === selId) ?? null;
  const cedulas = useMemo(
    () => Object.fromEntries((datos?.estudiantes ?? []).map((e) => [e.id_number, e.cedula ?? ''])),
    [datos],
  );

  /** Cambia el panel inmediatamente al estudiante de la alerta (sin esperar al backend). */
  const preparar = useCallback(
    (a: Alerta) => {
      peticion.current += 1; // invalida cualquier respuesta pendiente de otra alerta
      setParams({ alerta: String(a.id) }, { replace: true });
      setBorrador(borradorInicial(a, propuesta));
      setRefuerzoId(a.refuerzo_id);
      setOrigen(null);
      setGenerando(false);
      setError(null);
      setConfirmar(null);
    },
    [setParams, propuesta],
  );

  // Selección inicial por URL (?alerta=ID) o al cambiar de curso
  useEffect(() => {
    if (sel && borrador?.alertaId !== sel.id) preparar(sel);
    // Sólo se descarta la selección cuando las alertas cargadas ya son las del curso actual
    // (al cambiar de curso desde el chat, las del curso anterior siguen en memoria un instante).
    const alertasDelCurso = datos?.id === cursoId && alertas.every((a) => a.curso_id === cursoId);
    if (selId && !sel && alertas.length && alertasDelCurso) setParams({}, { replace: true });
  }, [sel, selId, alertas, borrador, preparar, setParams, datos, cursoId]);

  const atender = useCallback(
    async (a: Alerta) => {
      // Si el borrador viene del agente IA (chat), se conserva su texto: la atención sólo crea el refuerzo.
      const conservar = borrador?.alertaId === a.id && borrador.desdeAgente;
      if (conservar) {
        peticion.current += 1;
        setError(null);
      } else {
        preparar(a);
      }
      const n = peticion.current;
      setGenerando(true);
      try {
        const r = await endpoints.atenderAlerta(a.id);
        if (n !== peticion.current) return; // respuesta tardía de otra alerta: se descarta
        actualizarAlerta(r.alerta);
        setRefuerzoId(r.refuerzo.id);
        setOrigen(r.refuerzo.origen);
        setBorrador((b) =>
          b?.desdeAgente && b.alertaId === a.id
            ? b
            : {
                alertaId: a.id,
                titulo: r.refuerzo.titulo,
                instrucciones: r.refuerzo.instrucciones ?? r.refuerzo.descripcion ?? '',
                fechaEntrega: b?.fechaEntrega ?? fechaISOEnDias(7),
              },
        );
      } catch (ex) {
        if (n !== peticion.current) return;
        setError(ex instanceof ApiError ? ex.detail : 'No se pudo generar el borrador.');
      } finally {
        if (n === peticion.current) setGenerando(false);
      }
    },
    [preparar, actualizarAlerta, borrador],
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
            {nombreCurso(datos!.fullname)} · Alertas tempranas de nota crítica y descenso sostenido
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
        <section className="card stagger-1" aria-label="Listado de alertas">
          <div className="filtro-parcial" role="group" aria-label="Filtrar por parcial">
            {FILTROS_PARCIAL.map((f) => (
              <button
                key={f.valor}
                type="button"
                aria-pressed={parcial === f.valor}
                onClick={() => setParcial(f.valor)}
              >
                {f.etiqueta}
                <span className="num">
                  {alertas.filter((a) => coincide(a, filtro) && (f.valor === 'todos' || a.parcial === f.valor)).length}
                </span>
              </button>
            ))}
          </div>
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
              {/* Bloques: quién (nombre, C.I. y parcial) · métricas con etiqueta · acción en una columna de ancho fijo */}
              <div className="alerta-info">
                <div className="alerta-quien">
                  <strong>{a.nombres}</strong>
                  {cedulas[a.id_number] && <span className="muted small">C.I. {cedulas[a.id_number]}</span>}
                  {a.parcial && (
                    <span className={`badge parcial-badge parcial-${a.parcial}`} data-testid="parcial-alerta">
                      {NOMBRE_PARCIAL[a.parcial] ?? `Parcial ${a.parcial}`}
                    </span>
                  )}
                </div>
                <dl className="alerta-metricas">
                  <div>
                    <dt>Motivo</dt>
                    <dd>{REGLAS[a.regla] ?? a.regla}</dd>
                  </div>
                  <div>
                    <dt>Promedio</dt>
                    <dd className="num">{nota(a.nota_promedio)}/10</dd>
                  </div>
                  {a.unidad_critica && (
                    <div>
                      <dt>Unidad crítica</dt>
                      <dd>{a.unidad_critica}</dd>
                    </div>
                  )}
                  {a.regla === 'R2_DESCENSO' && a.pendiente !== null && (
                    <div>
                      <dt>Caída entre unidades</dt>
                      <dd className="num">
                        {a.pendiente >= 0 ? '+' : ''}
                        {a.pendiente.toFixed(2)}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
              <div className="alerta-accion">
                <EstadoAlertaBadge estado={a.estado} />
                {(a.estado === 'ABIERTA' || a.estado === 'ATENDIDA') && (
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={(e) => {
                      e.stopPropagation();
                      atender(a);
                    }}
                  >
                    {a.estado === 'ATENDIDA' ? 'Regenerar refuerzo' : 'Atender'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </section>

        <aside className="card panel-atencion stagger-2" aria-label="Panel de atención" aria-live="polite">
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
                    {cedulas[sel.id_number] ? `C.I. ${cedulas[sel.id_number]} · ` : ''}{sel.email}
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
                  La alerta es una señal para revisión docente, no una calificación definitiva. Detectada {fechaHora(sel.fecha_creacion).replace(/\.$/, '')}.
                </p>
                <div className="acciones-detalle">
                  <Link className="btn btn-sm" to={`/estudiantes/${sel.id_number}`}>
                    Ver ficha
                  </Link>
                  {sel.estado === 'PUBLICADO' && (publicaciones[sel.id]?.moodle_link ?? sel.moodle_url) && (
                    <a
                      className="btn btn-sm"
                      href={publicaciones[sel.id]?.moodle_link ?? sel.moodle_url ?? undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                      data-testid="ver-tarea-moodle"
                    >
                      Ver tarea en Moodle ↗
                    </a>
                  )}
                </div>

                {error && <Aviso tipo="error">{error}</Aviso>}

                {publicado ? (
                  <div className="publicado" data-testid="publicado">
                    <strong>✓ Tarea publicada en Moodle UTA</strong>
                    <span className="small">
                      Visible sólo para {sel.nombres}. Curso módulo (cmid): <b className="mono">{publicado.cmid}</b>
                    </span>
                    <span className="small">Fecha de entrega: {fechaHora(publicado.fecha_entrega)}</span>
                    {publicado.guia_pdf && (
                      <span className="small" data-testid="guia-pdf">
                        Guía de estudio adjunta en la tarea: <b className="mono">{publicado.guia_pdf}</b>
                      </span>
                    )}
                    <span className="small" data-testid="aviso-campana">
                      {publicado.notificado
                        ? `${sel.nombres} recibió el aviso en la campana de notificaciones de Moodle.`
                        : 'La tarea se publicó, pero Moodle no envió el aviso a la campana del estudiante.'}
                    </span>
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
                        <Spinner
                          etiqueta={
                            borrador.desdeAgente
                              ? `Registrando la atención de ${sel.nombres}…`
                              : `El agente está redactando el refuerzo para ${sel.nombres}…`
                          }
                        />
                      </Aviso>
                    )}
                    {borrador.desdeAgente && (
                      <span className="badge badge-blue" data-testid="propuesta-agente">
                        Propuesta preparada por el Agente IA desde el chat
                      </span>
                    )}
                    {!refuerzoId && !generando && (
                      <Aviso tipo="info">
                        <div>
                          {borrador.desdeAgente
                            ? 'Registre la atención para habilitar la publicación (se conserva la propuesta del agente).'
                            : 'Genere el borrador con el agente para poder publicarlo.'}{' '}
                          <button className="btn btn-sm btn-primary" onClick={() => atender(sel)} style={{ marginLeft: 6 }}>
                            {borrador.desdeAgente ? 'Registrar atención' : 'Atender'}
                          </button>
                        </div>
                      </Aviso>
                    )}
                    {origen && !borrador.desdeAgente && (
                      <span className="badge badge-blue" data-testid="origen-borrador">
                        Borrador sugerido por: Asistente Académico CoraIA
                      </span>
                    )}
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

      {/* RF-07 / Sección 13: carácter preventivo de las alertas */}
      <p className="nota-pedagogica" data-testid="nota-pedagogica">
        Las alertas son indicadores preventivos para revisión docente y no constituyen calificaciones ni diagnósticos
        definitivos.
      </p>

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
