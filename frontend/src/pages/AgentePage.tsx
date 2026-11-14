/**
 * RF-09 / RF-12: chat con el agente IA (POST /api/v1/agent/chat).
 * Muestra con transparencia qué herramientas reales invocó el agente, con qué parámetros y qué devolvieron.
 */

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { endpoints } from '../api/endpoints';
import type { ChatResponse, HerramientaCatalogo, HerramientaUsada } from '../api/types';
import { useChat, type MensajeChat } from '../context/ChatContext';
import { useCurso } from '../context/CursoContext';
import { fechaHora } from '../utils/formato';

const FUENTES: Record<string, string> = {
  ollama_slm: 'Plan del LLM local (Ollama)',
  'ollama_slm+reglas': 'Plan del LLM + reglas',
  reglas_deterministas: 'Plan por reglas deterministas',
};

export function sugerenciasPara(curso?: string, estudiante?: string): string[] {
  const c = curso ?? 'mis cursos';
  return [
    '¿Qué cursos tengo asignados?',
    `¿Qué estudiantes de ${c} necesitan atención?`,
    `Dame un resumen del curso ${c}`,
    `Muéstrame las calificaciones de ${c}`,
    ...(estudiante ? [`¿Cómo va ${estudiante}?`] : []),
  ];
}

export function AgentePage() {
  const { mensajes, enviando, enviar, limpiar } = useChat();
  const { cursoId, datos, sync } = useCurso();
  const [texto, setTexto] = useState('');
  const [catalogo, setCatalogo] = useState<HerramientaCatalogo[]>([]);
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endpoints.herramientas().then(setCatalogo).catch(() => setCatalogo([]));
  }, []);
  useEffect(() => {
    finRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [mensajes, enviando]);

  const curso = sync?.cursos.find((c) => c.id === cursoId);
  const critico = datos?.estudiantes.filter((e) => e.nivel_riesgo === 'CRITICO').sort((a, b) => a.nota_final - b.nota_final)[0];
  const sugerencias = sugerenciasPara(curso?.shortname, critico?.nombres);

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
          <p>Consultas en lenguaje natural respondidas sólo con datos reales del sistema · contexto: {curso?.shortname ?? 'todos sus cursos'}</p>
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
                <strong>Pregunte por sus cursos, calificaciones o estudiantes que requieren atención.</strong>
                <span>El agente elige qué herramientas usar; cada invocación queda registrada en el log del sistema.</span>
              </div>
            )}
            {mensajes.map((m) => (
              <Mensaje key={m.id} m={m} />
            ))}
            {enviando && (
              <div className="msg agente">
                <div className="burbuja">
                  <span className="spinner" aria-hidden /> El agente está planificando y consultando herramientas…
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
          <section className="card card-pad">
            <h3 style={{ marginBottom: 8 }}>Sugerencias</h3>
            <div className="sugerencias">
              {sugerencias.map((s) => (
                <button key={s} className="sugerencia" onClick={() => enviar(s, cursoId)} disabled={enviando}>
                  {s}
                </button>
              ))}
            </div>
          </section>
          <section className="card card-pad">
            <h3>Herramientas disponibles</h3>
            {catalogo.map((h) => (
              <div key={h.nombre} className="tool-cat">
                <span className="mono" style={{ color: 'var(--uta-blue)', fontWeight: 600 }}>
                  {h.nombre}
                </span>
                <span className="muted">{h.descripcion}</span>
              </div>
            ))}
            {catalogo.length === 0 && <p className="muted small">No disponible.</p>}
          </section>
        </aside>
      </div>
    </>
  );
}

function Mensaje({ m }: { m: MensajeChat }) {
  return (
    <div className={`msg ${m.rol}`}>
      <div className="burbuja">{m.texto}</div>
      <div className="msg-meta">
        <span>{m.rol === 'docente' ? 'Usted' : m.rol === 'agente' ? 'Agente EduMonitor' : 'Error'}</span>
        <span>· {fechaHora(m.fecha)}</span>
        {m.detalle && <Trazabilidad r={m.detalle} />}
      </div>
      {m.detalle && m.detalle.herramientas.length > 0 && <Herramientas lista={m.detalle.herramientas} />}
    </div>
  );
}

function Trazabilidad({ r }: { r: ChatResponse }) {
  return (
    <>
      <span className="badge badge-blue" title={r.plan_fuente}>
        {FUENTES[r.plan_fuente] ?? r.plan_fuente}
      </span>
      <span>· {(r.duracion_ms / 1000).toFixed(1)} s</span>
      <span>· redacción desde herramientas, sin texto inventado</span>
    </>
  );
}

function Herramientas({ lista }: { lista: HerramientaUsada[] }) {
  return (
    <details className="herramientas">
      <summary>
        Herramientas invocadas ({lista.length}): {lista.map((h) => h.herramienta).join(', ')}
      </summary>
      {lista.map((h, i) => (
        <div key={`${h.herramienta}-${i}`} className="herramienta" data-testid="herramienta-usada">
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="badge badge-neutral">#{i + 1}</span>
            <span className="mono" style={{ fontWeight: 600 }}>
              {h.herramienta}
            </span>
            {h.resultado?.error ? (
              <span className="badge nivel-critico">error: {h.resultado.error}</span>
            ) : (
              <span className="muted">{h.resultado?.filas ?? 0} fila(s) devueltas</span>
            )}
          </div>
          <div>
            <span className="muted">Parámetros</span>
            <pre>{JSON.stringify(h.parametros, null, 2)}</pre>
          </div>
          <details>
            <summary style={{ padding: 0, fontWeight: 500 }}>Ver resultado</summary>
            <pre>{JSON.stringify(h.resultado, null, 2)}</pre>
          </details>
        </div>
      ))}
    </details>
  );
}
