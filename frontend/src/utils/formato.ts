const ZONA = 'America/Guayaquil';

/** Fecha y hora en hora de Ecuador (UTC-5). */
export function fechaHora(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('es-EC', {
    timeZone: ZONA,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function fecha(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('es-EC', { timeZone: ZONA, day: '2-digit', month: 'long', year: 'numeric' });
}

/** Hace cuánto (p. ej. "hace 5 min"). */
export function haceCuanto(iso: string | null | undefined, ahora = Date.now()): string {
  if (!iso) return 'nunca';
  const seg = Math.round((ahora - new Date(iso).getTime()) / 1000);
  if (Number.isNaN(seg)) return '';
  if (seg < 60) return 'hace instantes';
  if (seg < 3600) return `hace ${Math.floor(seg / 60)} min`;
  if (seg < 86400) return `hace ${Math.floor(seg / 3600)} h`;
  return `hace ${Math.floor(seg / 86400)} d`;
}

export function nota(n: number | null | undefined): string {
  return n === null || n === undefined ? '—' : n.toFixed(2);
}

/** Fecha local AAAA-MM-DD sumando días a hoy (para el selector de fecha de entrega). */
export function fechaISOEnDias(dias: number, base = new Date()): string {
  const d = new Date(base);
  d.setDate(d.getDate() + dias);
  const p = (x: number) => String(x).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function iniciales(nombre: string): string {
  return nombre
    .replace(/^(Ing\.|Dr\.|Mg\.|Lic\.)\s*/i, '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}
