/**
 * Chat con el agente IA (POST /api/v1/agent/chat).
 * Respuestas estructuradas (Markdown seguro) y, bajo cada una, un acordeón colapsado de auditoría con las
 * fuentes consultadas; los parámetros JSON y los registros sólo se ven al expandirlo.
 */

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { endpoints } from '../api/endpoints';
import type { AdjuntoChat, ChatResponse, HerramientaUsada, PropuestaRefuerzo } from '../api/types';
import { useChat, type MensajeChat } from '../context/ChatContext';
import { useCurso } from '../context/CursoContext';
import { useAuth } from '../context/AuthContext';
import { Markdown } from '../components/ui/Markdown';
import { fechaHora, haceCuanto } from '../utils/formato';
import { materiaCurso, partesCurso } from '../utils/nombres';

export const NOMBRES_HERRAMIENTAS: Record<string, string> = {
  listar_cursos_autorizados: 'Cursos autorizados del docente',
  obtener_calificaciones: 'Calificaciones sincronizadas',
  identificar_alertas: 'Alertas tempranas',
  generar_resumen: 'Resumen del curso',
  analizar_actividades: 'Rendimiento por actividad',
  proponer_refuerzo: 'Propuesta de refuerzo',
  listar_estudiantes: 'Nómina del curso',
  perfil_docente: 'Perfil del docente',
  generar_guia_pdf: 'Guía oficial de refuerzo (PDF)',
};

const FUENTES: Record<string, string> = {
  ollama_slm: 'plan del LLM local (Ollama)',
  'ollama_slm+reglas': 'plan del LLM local + reglas',
  reglas_deterministas: 'plan por reglas deterministas',
  ollama_rag: 'respuesta redactada por el LLM local (Ollama) sólo con los datos reales consultados',
  datos_relacionados: 'datos reales relacionados con la pregunta (sin interpretación del LLM)',
};

export interface GrupoSugerencias {
  titulo: string;
  preguntas: string[];
}

export function sugerenciasPara(curso?: string, estudiante?: string): GrupoSugerencias[] {
  const c = curso ?? 'mi curso';
  const e = estudiante ?? 'Carlos Mendoza';
  return [
    { titulo: 'Panorama general', preguntas: ['¿Cuántos cursos y estudiantes tengo en total?', `Dame un resumen del curso ${c}`] },
    {
      titulo: 'Seguimiento de estudiantes',
      preguntas: [`¿Qué estudiantes de ${c} necesitan atención?`, `¿Cómo va ${e} en mis materias?`],
    },
    { titulo: 'Actividades', preguntas: [`¿Qué actividades tienen menor rendimiento en ${c}?`] },
    { titulo: 'Intervención', preguntas: [`Prepárame un plan de apoyo para ${e}`] },
  ];
}

export function AgentePage() {
  const { mensajes, enviando, enviar, limpiar } = useChat();
  const { cursoId, datos, sync, alertas } = useCurso();
  const { usuario } = useAuth();
  const nombre = usuario?.nombres?.split(/\s+/)[0];
  const [texto, setTexto] = useState('');
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [mensajes, enviando]);

  const curso = sync?.cursos.find((c) => c.id === cursoId);
  const critico = datos?.estudiantes.filter((e) => e.nivel_riesgo === 'CRITICO').sort((a, b) => a.nota_final - b.nota_final)[0];
  const grupos = sugerenciasPara(curso ? materiaCurso(curso.fullname) : undefined, critico?.nombres);
  const activas = alertas.filter((a) => a.estado === 'ABIERTA' || a.estado === 'ATENDIDA').length;

  function enviarForm(e: FormEvent) {
    e.preventDefault();
    if (!texto.trim() || enviando) return;
    enviar(texto, cursoId);
    setTexto('');
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>CoraIA</h1>
          <p>Consultas en lenguaje natural respondidas sólo con datos reales sincronizados desde Moodle UTA</p>
        </div>
        {mensajes.length > 0 && (
          <button className="btn btn-sm" onClick={limpiar}>
            Nueva conversación
          </button>
        )}
      </div>

      <div className="chat-layout">
        <section className="card chat-card stagger-1" aria-label="Conversación con el agente">
          <div className="chat-hist" role="log" aria-live="polite">
            {mensajes.length === 0 && (
              // Bienvenida en español (idioma de la interfaz); CoraIA responde en inglés si el docente escribe en inglés
              <div className="msg agente bienvenida" data-testid="bienvenida">
                <div className="burbuja">
                  <div className="md">
                    <p>
                      <strong>¡Hola{nombre ? `, ${nombre}` : ''}!</strong> Soy CoraIA, el asistente académico de la UTA - FISEI.
                    </p>
                    <p>
                      Puedo consultar sus cursos, las calificaciones de sus estudiantes, las alertas tempranas y preparar guías
                      de refuerzo. ¿En qué le ayudo hoy?
                    </p>
                    <p className="muted small">Puede escribirme en español o en inglés: respondo en el idioma de su pregunta.</p>
                  </div>
                </div>
              </div>
            )}
            {mensajes.map((m) => (
              <Mensaje key={m.id} m={m} />
            ))}
            {enviando && (
              <div className="msg agente">
                <div className="burbuja">
                  <span className="spinner" aria-hidden /> Analizando los datos de sus cursos…
                </div>
              </div>
            )}
            <div ref={finRef} />
          </div>
          <form className="chat-form" onSubmit={enviarForm}>
            <label className="sr-only" htmlFor="chat-input">
              Mensaje para el agente
            </label>
            <input
              id="chat-input"
              className="input"
              placeholder="Escriba su consulta…"
              value={texto}
              maxLength={1000}
              onChange={(e) => setTexto(e.target.value)}
              disabled={enviando}
            />
            <button className="btn btn-primary" type="submit" disabled={enviando || !texto.trim()}>
              Enviar
            </button>
          </form>
        </section>

        <aside className="grid" style={{ gap: 16 }}>
          <section className="card card-pad contexto-activo stagger-2" aria-label="Contexto activo">
            <h3>Contexto activo</h3>
            {curso ? (
              <dl>
                <dt>Curso</dt>
                <dd data-testid="contexto-curso">{partesCurso(curso.fullname).materia}</dd>
                {partesCurso(curso.fullname).paralelo && (
                  <>
                    <dt>Paralelo</dt>
                    <dd data-testid="contexto-paralelo">{partesCurso(curso.fullname).paralelo}</dd>
                  </>
                )}
                <dt>Estudiantes</dt>
                <dd>{curso.total_estudiantes}</dd>
                <dt>Promedio</dt>
                <dd>{curso.promedio.toFixed(2)}/10</dd>
                <dt>Alertas por atender</dt>
                <dd>{activas}</dd>
                <dt>Datos</dt>
                <dd>sincronizados {haceCuanto(sync?.ultima_sincronizacion)}</dd>
              </dl>
            ) : (
              <p className="muted small">Sin curso seleccionado: se consultan todos sus cursos.</p>
            )}
          </section>
          <section className="card card-pad stagger-3" aria-label="Preguntas sugeridas">
            <h3 style={{ marginBottom: 6 }}>Preguntas sugeridas</h3>
            {grupos.map((g) => (
              <div key={g.titulo} className="grupo-sugerencias">
                <span className="grupo-titulo">{g.titulo}</span>
                <div className="sugerencias">
                  {g.preguntas.map((s) => (
                    <button key={s} className="sugerencia" onClick={() => enviar(s, cursoId)} disabled={enviando}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </section>
        </aside>
      </div>
    </>
  );
}

function Mensaje({ m }: { m: MensajeChat }) {
  const propuesta = m.detalle?.herramientas.find((h) => h.herramienta === 'proponer_refuerzo' && !h.resultado?.error)
    ?.resultado as unknown as PropuestaRefuerzo | undefined;
  return (
    <div className={`msg ${m.rol}`}>
      <div className="burbuja">
        {m.rol === 'agente' && m.detalle?.formato === 'markdown' ? <Markdown texto={m.texto} /> : m.texto}
        {m.detalle?.adjuntos?.map((a) => <Adjunto key={a.url} a={a} />)}
      </div>
      {propuesta && <AccionPropuesta p={propuesta} />}
      <div className="msg-meta">
        <span>{m.rol === 'docente' ? 'Usted' : m.rol === 'agente' ? 'CoraIA' : 'Error'}</span>
        <span>· {fechaHora(m.fecha)}</span>
      </div>
      {m.detalle && m.detalle.herramientas.length > 0 && <Auditoria r={m.detalle} />}
    </div>
  );
}

/**
 * Archivo adjunto a la respuesta (guía oficial en PDF): se pide con el JWT (un enlace directo no llevaría la
 * cabecera Authorization) y se abre en otra pestaña o se descarga sin salir del Agente IA.
 */
export function Adjunto({ a }: { a: AdjuntoChat }) {
  const [cargando, setCargando] = useState<'abrir' | 'descargar' | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function obtener(modo: 'abrir' | 'descargar') {
    setCargando(modo);
    setError(null);
    // La pestaña se abre en el mismo clic (si se abre tras la descarga, el navegador la bloquea)
    const pestana = modo === 'abrir' ? window.open('', '_blank') : null;
    try {
      const resp = await endpoints.archivo(a.url);
      const url = URL.createObjectURL(await resp.blob());
      if (pestana) {
        pestana.location.href = url;
      } else {
        const enlace = document.createElement('a');
        enlace.href = url;
        enlace.download = a.nombre;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (ex) {
      pestana?.close();
      setError(ex instanceof ApiError ? ex.detail : 'No se pudo obtener el PDF.');
    } finally {
      setCargando(null);
    }
  }

  return (
    <div className="adjunto-chat" data-testid="adjunto-pdf">
      <span className="adjunto-icono" aria-hidden>
        PDF
      </span>
      <span className="adjunto-nombre">{a.nombre}</span>
      <span className="adjunto-acciones">
        <button className="btn btn-sm" onClick={() => obtener('abrir')} disabled={cargando !== null}>
          {cargando === 'abrir' && <span className="spinner" aria-hidden />} Abrir
        </button>
        <button className="btn btn-sm btn-primary" onClick={() => obtener('descargar')} disabled={cargando !== null}>
          {cargando === 'descargar' && <span className="spinner" aria-hidden />} {a.etiqueta ?? 'Descargar PDF'}
        </button>
      </span>
      {error && (
        <span className="adjunto-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

/** Lleva la propuesta del agente al Centro de alertas para revisarla y publicarla en Moodle. */
function AccionPropuesta({ p }: { p: PropuestaRefuerzo }) {
  const navegar = useNavigate();
  const { cursoId, seleccionarCurso } = useCurso();
  const aplicable = p.alerta && (p.alerta.estado === 'ABIERTA' || p.alerta.estado === 'ATENDIDA');
  if (!aplicable) return null;
  function aplicar() {
    if (p.curso_id !== cursoId) seleccionarCurso(p.curso_id);
    navegar(`/alertas?alerta=${p.alerta!.id}`, {
      state: { propuesta: { alertaId: p.alerta!.id, titulo: p.propuesta.titulo, instrucciones: p.propuesta.instrucciones } },
    });
  }
  return (
    <div className="accion-propuesta">
      <span>
        Propuesta lista para <strong>{p.estudiante.nombres}</strong> en {p.curso}.
      </span>
      <button className="btn btn-sm btn-primary" onClick={aplicar}>
        Aplicar en el Centro de alertas
      </button>
    </div>
  );
}

function Auditoria({ r }: { r: ChatResponse }) {
  const nombres = r.herramientas.map((h) => NOMBRES_HERRAMIENTAS[h.herramienta] ?? h.herramienta);
  return (
    <details className="auditoria" data-testid="auditoria">
      <summary>
        <span className="auditoria-titulo">Fuentes consultadas / Trazabilidad</span>
        <span className="auditoria-resumen">
          {nombres.join(' · ')} · {(r.duracion_ms / 1000).toFixed(1)} s
        </span>
      </summary>
      <div className="auditoria-cuerpo">
        <p className="small muted">
          Origen del plan: {FUENTES[r.plan_fuente] ?? r.plan_fuente}. La respuesta se redactó únicamente con los resultados de
          estas consultas; cada invocación quedó registrada en el log del sistema.
        </p>
        {r.herramientas.map((h, i) => (
          <FuenteConsultada key={`${h.herramienta}-${i}`} h={h} n={i + 1} />
        ))}
      </div>
    </details>
  );
}

/** «curso: SOF-POO-A · docente_id: 2» (parámetros ya validados por el middleware; nunca incluye secretos). */
function parametrosLegibles(p: Record<string, unknown>): string {
  return Object.entries(p)
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' · ');
}

function FuenteConsultada({ h, n }: { h: HerramientaUsada; n: number }) {
  const filas = h.resultado?.filas ?? 0;
  const t = h.trazabilidad;
  return (
    <div className="herramienta" data-testid="herramienta-usada">
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="badge badge-neutral">#{n}</span>
        <strong>{NOMBRES_HERRAMIENTAS[h.herramienta] ?? h.herramienta}</strong>
        {h.resultado?.error ? (
          <span className="badge nivel-critico">sin resultado: {h.resultado.error}</span>
        ) : (
          <span className="muted">
            {filas} {filas === 1 ? 'registro' : 'registros'}
            {h.duracion_ms !== undefined ? ` · ${h.duracion_ms} ms` : ''}
          </span>
        )}
      </div>
      {t && (
        <dl className="trazabilidad" data-testid="trazabilidad">
          <dt>Herramienta invocada</dt>
          <dd className="mono">{t.herramienta}</dd>
          <dt>Parámetros validados</dt>
          <dd>{parametrosLegibles(t.parametros_validados)}</dd>
          <dt>Estado y fuente</dt>
          <dd>
            <span className={t.estado === 'OK' ? 'traza-ok' : 'traza-error'}>{t.estado}</span> · {t.resultado} · {t.fuente}
          </dd>
        </dl>
      )}
      <details>
        <summary className="small">Ver parámetros y registros</summary>
        <div className="small muted">
          Herramienta: <span className="mono">{h.herramienta}</span>
        </div>
        <span className="muted small">Parámetros</span>
        <pre>{JSON.stringify(h.parametros, null, 2)}</pre>
        <span className="muted small">Registros devueltos</span>
        <pre>{JSON.stringify(h.resultado, null, 2)}</pre>
      </details>
    </div>
  );
}
