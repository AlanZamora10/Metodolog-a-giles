/**
 * Renderizador Markdown mínimo y seguro para las respuestas del agente (sin innerHTML).
 * Soporta: "### título", viñetas "- " (con un nivel de anidación "  - "), listas "1. ",
 * párrafos, **negritas** y *cursivas*.
 */

import type { ReactNode } from 'react';

function enLinea(texto: string, clave: string): ReactNode[] {
  const partes: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|\*(.+?)\*/g;
  let ultimo = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(texto))) {
    if (m.index > ultimo) partes.push(texto.slice(ultimo, m.index));
    partes.push(m[1] !== undefined ? <strong key={`${clave}-b${i++}`}>{m[1]}</strong> : <em key={`${clave}-i${i++}`}>{m[2]}</em>);
    ultimo = re.lastIndex;
  }
  if (ultimo < texto.length) partes.push(texto.slice(ultimo));
  return partes;
}

type Bloque =
  | { tipo: 'h'; texto: string }
  | { tipo: 'p'; texto: string }
  | { tipo: 'ul'; items: { texto: string; hijos: string[] }[] }
  | { tipo: 'ol'; items: string[] };

export function parsearMarkdown(fuente: string): Bloque[] {
  const bloques: Bloque[] = [];
  for (const cruda of fuente.replace(/\r/g, '').split('\n')) {
    const linea = cruda.trimEnd();
    const ultimo = bloques[bloques.length - 1];
    if (!linea.trim()) {
      bloques.push({ tipo: 'p', texto: '' });
      continue;
    }
    let m: RegExpMatchArray | null;
    if ((m = linea.match(/^#{1,4}\s+(.*)$/))) {
      bloques.push({ tipo: 'h', texto: m[1] });
    } else if ((m = linea.match(/^\s{2,}[-*]\s+(.*)$/)) && ultimo?.tipo === 'ul') {
      ultimo.items[ultimo.items.length - 1].hijos.push(m[1]);
    } else if ((m = linea.match(/^[-*]\s+(.*)$/))) {
      if (ultimo?.tipo === 'ul') ultimo.items.push({ texto: m[1], hijos: [] });
      else bloques.push({ tipo: 'ul', items: [{ texto: m[1], hijos: [] }] });
    } else if ((m = linea.match(/^\d+\.\s+(.*)$/))) {
      if (ultimo?.tipo === 'ol') ultimo.items.push(m[1]);
      else bloques.push({ tipo: 'ol', items: [m[1]] });
    } else if (ultimo?.tipo === 'p' && ultimo.texto) {
      ultimo.texto += `\n${linea}`;
    } else {
      bloques.push({ tipo: 'p', texto: linea });
    }
  }
  return bloques.filter((b) => b.tipo !== 'p' || b.texto);
}

export function Markdown({ texto }: { texto: string }) {
  return (
    <div className="md">
      {parsearMarkdown(texto).map((b, i) => {
        const k = `b${i}`;
        if (b.tipo === 'h') return <h4 key={k}>{enLinea(b.texto, k)}</h4>;
        if (b.tipo === 'p') return <p key={k}>{enLinea(b.texto, k)}</p>;
        if (b.tipo === 'ol')
          return (
            <ol key={k}>
              {b.items.map((t, j) => (
                <li key={j}>{enLinea(t, `${k}-${j}`)}</li>
              ))}
            </ol>
          );
        return (
          <ul key={k}>
            {b.items.map((it, j) => (
              <li key={j}>
                {enLinea(it.texto, `${k}-${j}`)}
                {it.hijos.length > 0 && (
                  <ul>
                    {it.hijos.map((h, n) => (
                      <li key={n}>{enLinea(h, `${k}-${j}-${n}`)}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        );
      })}
    </div>
  );
}
