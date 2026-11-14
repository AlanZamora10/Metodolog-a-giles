/**
 * Gráficos del dashboard y la ficha del estudiante (Recharts).
 * Una sola serie por gráfico (azul UTA) con tooltip; líneas de referencia en 5.00 (crítico) y 7.00 (aprobación).
 * Los estados de actividad usan la paleta validada para daltonismo y siempre llevan etiqueta + conteo.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from 'recharts';
import { ESTADOS_VISUALES, ORDEN_ESTADOS, type EstadoVisual } from '../../utils/academico';

const AZUL = '#11297A';
const EJE = { fontSize: 12, fill: '#6A737B' };

function Tip({ active, payload, label, sufijo }: TooltipProps<number, string> & { sufijo?: string }) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  const extra = (p.payload as { nombre?: string; detalle?: string }) ?? {};
  return (
    <div className="tooltip">
      <strong>{extra.nombre ?? label}</strong>
      {extra.detalle && <div className="muted">{extra.detalle}</div>}
      <span className="num">
        {p.value === null || p.value === undefined ? 'sin nota' : `${p.value}${sufijo ?? ''}`}
      </span>
    </div>
  );
}

// Recharts sólo reconoce sus elementos como hijos directos (no envueltos en otro componente):
// por eso las líneas de referencia se insertan como un arreglo.
const REFERENCIAS = [
  <ReferenceLine key="r5" y={5} stroke="#B02A2A" strokeDasharray="4 4" ifOverflow="extendDomain"
    label={{ value: 'crítico 5.00', position: 'insideTopRight', fontSize: 11, fill: '#B02A2A' }} />,
  <ReferenceLine key="r7" y={7} stroke="#1E7B34" strokeDasharray="4 4" ifOverflow="extendDomain"
    label={{ value: 'aprobación 7.00', position: 'insideTopRight', fontSize: 11, fill: '#1E7B34' }} />,
];

/** Histograma de notas finales (estudiantes por tramo). */
export function DistribucionNotas({ datos }: { datos: { tramo: string; estudiantes: number }[] }) {
  return (
    <div className="chart-box" role="img" aria-label={`Distribución de notas: ${datos.map((d) => `${d.tramo}: ${d.estudiantes}`).join(', ')}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={datos} margin={{ top: 8, right: 8, left: -18, bottom: 0 }} barCategoryGap="18%">
          <CartesianGrid vertical={false} stroke="#E9ECEF" />
          <XAxis dataKey="tramo" tick={EJE} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={EJE} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: '#EEF1F9' }} content={<Tip sufijo=" estudiante(s)" />} />
          <Bar isAnimationActive={false} dataKey="estudiantes" fill={AZUL} radius={[4, 4, 0, 0]} maxBarSize={56} label={{ position: 'top', fontSize: 12, fill: '#495057' }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Barras de promedio /10 por categoría (unidad, actividad o componente). */
export function BarrasPromedio({ datos, clave, alto = 260 }: { datos: Record<string, unknown>[]; clave: string; alto?: number }) {
  return (
    <div style={{ height: alto }} role="img" aria-label={datos.map((d) => `${d[clave]}: ${d.promedio}`).join(', ')}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={datos} margin={{ top: 14, right: 8, left: -18, bottom: 0 }} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke="#E9ECEF" />
          <XAxis dataKey={clave} tick={EJE} axisLine={false} tickLine={false} interval={0} />
          <YAxis domain={[0, 10]} ticks={[0, 2, 4, 6, 8, 10]} tick={EJE} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: '#EEF1F9' }} content={<Tip sufijo=" /10" />} />
          {REFERENCIAS}
          <Bar isAnimationActive={false} dataKey="promedio" fill={AZUL} radius={[4, 4, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Evolución de notas de un estudiante por actividad (los huecos son actividades sin nota). */
export function EvolucionEstudiante({ datos }: { datos: { actividad: string; nota: number | null; nombre: string; detalle: string }[] }) {
  return (
    <div className="chart-box" role="img" aria-label={`Evolución de notas: ${datos.map((d) => `${d.actividad} ${d.nota ?? 'sin nota'}`).join(', ')}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={datos} margin={{ top: 14, right: 28, left: -18, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#E9ECEF" />
          <XAxis dataKey="actividad" tick={EJE} axisLine={false} tickLine={false} interval={0} />
          <YAxis domain={[0, 10]} ticks={[0, 2, 4, 6, 8, 10]} tick={EJE} axisLine={false} tickLine={false} />
          <Tooltip content={<Tip sufijo=" /10" />} />
          {REFERENCIAS}
          <Line isAnimationActive={false} type="linear" dataKey="nota" stroke={AZUL} strokeWidth={2} dot={{ r: 4, fill: AZUL, stroke: '#fff', strokeWidth: 2 }} activeDot={{ r: 6 }} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Barra apilada horizontal de estados + leyenda con conteos (identidad nunca sólo por color). */
export function DesgloseEstados({ conteo }: { conteo: Record<EstadoVisual, number> }) {
  const total = ORDEN_ESTADOS.reduce((s, k) => s + conteo[k], 0);
  return (
    <div>
      <div className="barra-estados" role="img" aria-label={ORDEN_ESTADOS.map((k) => `${ESTADOS_VISUALES[k].etiqueta}: ${conteo[k]}`).join(', ')}>
        {total === 0 && <div style={{ flex: 1, background: '#E9ECEF' }} />}
        {ORDEN_ESTADOS.filter((k) => conteo[k] > 0).map((k) => (
          <div key={k} style={{ flex: conteo[k], background: ESTADOS_VISUALES[k].color }} title={`${ESTADOS_VISUALES[k].etiqueta}: ${conteo[k]}`} />
        ))}
      </div>
      <div className="leyenda-estados">
        {ORDEN_ESTADOS.map((k) => (
          <div key={k} data-testid={`estado-${k}`}>
            <span className="estado-icono" style={{ background: ESTADOS_VISUALES[k].color }} aria-hidden>
              {ESTADOS_VISUALES[k].icono}
            </span>
            <span>{ESTADOS_VISUALES[k].etiqueta}</span>
            <b>{conteo[k]}</b>
          </div>
        ))}
      </div>
    </div>
  );
}
