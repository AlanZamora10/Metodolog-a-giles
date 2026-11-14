/**
 * RF-09 / RF-12: chat con el agente IA (POST /api/v1/agent/chat).
 * Respuestas estructuradas (Markdown seguro) y, bajo cada una, un acordeón colapsado de auditoría con las
 * fuentes consultadas; los parámetros JSON y los registros sólo se ven al expandirlo.
 */

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import type { ChatResponse, HerramientaUsada, PropuestaRefuerzo } from '../api/types';
import { useChat, type MensajeChat } from '../context/ChatContext';
import { useCurso } from '../context/CursoContext';
import { Markdown } from '../components/ui/Markdown';
import { fechaHora, haceCuanto } from '../utils/formato';

export const NOMBRES_HERRAMIENTAS: Record<string, string> = {
  listar_cursos_autorizados: 'Cursos autorizados del docente',
  obtener_calificaciones: 'Calificaciones sincronizadas',
  identificar_alertas: 'Alertas tempranas',
  generar_resumen: 'Resumen del curso',
  analizar_actividades: 'Rendimiento por actividad',
  proponer_refuerzo: 'Propuesta de refuerzo',
};

const FUENTES: Record<string, string> = {
  ollama_slm: 'plan del LLM local (Ollama)',
  'ollama_slm+reglas': 'plan del LLM local + reglas',
  reglas_deterministas: 'plan por reglas deterministas',
};

export interface GrupoSugerencias {
  titulo: string;
  preguntas: string[];
}

export function sugerenciasPara(curso?: string, estudiante?: string): GrupoSugerencias[] {
  const c = curso ?? 'mi curso';
  const e = estudiante ?? 'Diego Curillo';
  return [
    { titulo: 'Panorama general', preguntas: ['¿Cuántos cursos y estudiantes tengo en total?', `Dame un resumen del curso ${c}`] },
    {
      titulo: 'Seguimiento de estudiantes',
      preguntas: [`¿Qué estudiantes de ${c} necesitan atención?`, `¿Cómo va ${e} en mis materias?`],
    },
    { titulo: 'Actividades', preguntas: [`¿Qué actividades tienen menor rendimiento en ${c}?`] },
    { titulo: 'Intervención', preguntas: [`Prepárame una actividad de refuerzo para ${e}`] },
  ];
}

export function AgentePage() {
  const { mensajes, enviando, enviar, limpiar } = useChat();
  const { cursoId, datos, sync, alertas } = useCurso();
  const [texto, setTexto] = useState('');
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [mensajes, enviando]);

  const curso = sync?.cursos.find((c) => c.id === cursoId);
  const critico = datos?.estudiantes.filter((e) => e.nivel_riesgo === 'CRITICO').sort((a, b) => a.nota_final - b.nota_final)[0];
  const grupos = sugerenciasPara(curso?.shortname, critico?.nombres);
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
          <h1>Agente IA</h1>
          <p>Consultas en lenguaje natural respondidas sólo con datos reales sincronizados desde Moodle UTA</p>
        </div>
        {mensajes.length > 0 && (
          <button className="btn btn-sm" onClick={limpiar}>
            Nueva conversación
          </button>
        )}
      </div>

      <div className="chat-layout">
        <section className="card chat-card" aria-label="Conversación con el agente">
          <div className="chat-hist" role="log" aria-live="polite">
            {mensajes.length === 0 && (
              <div className="empty">
                <strong>¿En qué le ayudo hoy?</strong>
                <span>Pregunte por sus cursos, estudiantes, actividades o pídame preparar un refuerzo.</span>
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
          <section className="card card-pad contexto-activo" aria-label="Contexto activo">
            <h3>Contexto activo</h3>
            {curso ? (
              <dl>
                <dt>Curso</dt>
                <dd>{curso.shortname}</dd>
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
            <p className="small muted" style={{ marginTop: 8 }}>
              Las preguntas sobre «todos mis cursos» o sobre un estudiante consultan los {sync?.cursos.length ?? 0} cursos.
            </p>
          </section>
          <section className="card card-pad" aria-label="Preguntas sugeridas">
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
      </div>
      {propuesta && <AccionPropuesta p={propuesta} />}
      <div className="msg-meta">
        <span>{m.rol === 'docente' ? 'Usted' : m.rol === 'agente' ? 'Agente EduMonitor' : 'Error'}</span>
        <span>· {fechaHora(m.fecha)}</span>
      </div>
      {m.detalle && m.detalle.herramientas.length > 0 && <Auditoria r={m.detalle} />}
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
        <span className="auditoria-titulo">Auditoría y fuentes consultadas (RF-12)</span>
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

function FuenteConsultada({ h, n }: { h: HerramientaUsada; n: number }) {
  return (
    <div className="herramienta" data-testid="herramienta-usada">
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="badge badge-neutral">#{n}</span>
        <strong>{NOMBRES_HERRAMIENTAS[h.herramienta] ?? h.herramienta}</strong>
        {h.resultado?.error ? (
          <span className="badge nivel-critico">sin resultado: {h.resultado.error}</span>
        ) : (
          <span className="muted">
            {h.resultado?.filas ?? 0} registro(s){h.duracion_ms !== undefined ? ` · ${h.duracion_ms} ms` : ''}
          </span>
        )}
      </div>
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
