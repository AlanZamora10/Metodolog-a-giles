import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCurso } from '../context/CursoContext';
import { CursoRequerido } from '../components/layout/CursoRequerido';
import { NivelBadge } from '../components/ui/ui';
import { actividadesEnCorte, contarEstados, metricasEnCorte, REGLAS } from '../utils/academico';
import type { MetricasEstudiante as Metricas } from '../api/types';
import { nota } from '../utils/formato';
import { nombreCurso } from '../utils/nombres';

/** Listado de estudiantes del curso con buscador (cédula o nombre completo) y filtros. */
export function EstudiantesPage() {
  return (
    <CursoRequerido>
      <Listado />
    </CursoRequerido>
  );
}

const normalizar = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();

/** Coincidencia por cédula (dígitos, admite búsqueda parcial) o por nombre completo (sin tildes). */
export function coincideBusqueda(e: { nombres: string; cedula?: string | null }, consulta: string): boolean {
  const q = normalizar(consulta);
  if (!q) return true;
  const digitos = q.replace(/\D/g, '');
  if (digitos && digitos.length === q.replace(/[\s.-]/g, '').length) return (e.cedula ?? '').includes(digitos);
  const nombre = normalizar(e.nombres);
  if (nombre.includes(q)) return true;
  // Nombre completo (dos nombres y dos apellidos): «carlos mendoza» o «mendoza par» también lo encuentran,
  // cada palabra escrita debe ser el inicio de alguna palabra del nombre.
  const palabras = nombre.split(/\s+/);
  return q.split(/\s+/).every((t) => palabras.some((p) => p.startsWith(t)));
}

const TENDENCIAS = { SUBE: ['↗', 'Sube'], BAJA: ['↘', 'Baja'], ESTABLE: ['→', 'Estable'] } as const;

/** «↗ Sube (+0.54)» en una sola línea. */
function Tendencia({ m }: { m: Metricas }) {
  const [flecha, texto] = TENDENCIAS[m.tendencia as keyof typeof TENDENCIAS] ?? TENDENCIAS.ESTABLE;
  return (
    <span className={`tendencia tendencia-${m.tendencia.toLowerCase()}`} data-testid="tendencia">
      <span aria-hidden>{flecha}</span> {texto} <span className="num">({m.pendiente >= 0 ? '+' : ''}{m.pendiente.toFixed(2)})</span>
    </span>
  );
}

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

function Listado() {
  const { datos, corte } = useCurso();
  const navegar = useNavigate();
  const [busqueda, setBusqueda] = useState('');
  const [nivel, setNivel] = useState('');
  const [regla, setRegla] = useState('');
  const [conIncidencias, setConIncidencias] = useState(false);

  const filas = useMemo(() => {
    return datos!.estudiantes
      .map((e) => {
        const m = metricasEnCorte(e, corte);
        const estados = contarEstados(actividadesEnCorte(e, corte));
        return { e, m, estados, incidencias: estados.cero + estados.sin_entrega + estados.pendiente };
      })
      .filter(({ e, m, incidencias }) => {
        if (!coincideBusqueda(e, busqueda)) return false;
        if (nivel && m?.nivel_riesgo !== nivel) return false;
        if (regla === 'ninguna' ? e.regla_alerta : regla && e.regla_alerta !== regla) return false;
        if (conIncidencias && incidencias === 0) return false;
        return true;
      })
      .sort((a, b) => a.e.nombres.localeCompare(b.e.nombres, 'es'));
  }, [datos, corte, busqueda, nivel, regla, conIncidencias]);

  const limpiar = () => {
    setBusqueda('');
    setNivel('');
    setRegla('');
    setConIncidencias(false);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Estudiantes</h1>
          <p>
            {nombreCurso(datos!.fullname)} · {datos!.estudiantes.length} matriculados en Moodle UTA
          </p>
        </div>
      </div>

      <section className="card stagger-1">
        <div className="card-body filtros" style={{ paddingTop: 16 }}>
          <label className="field">
            <span>Buscar</span>
            <input
              className="input buscar"
              type="search"
              placeholder="Cédula o nombre completo"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Nivel</span>
            <select className="select" value={nivel} onChange={(e) => setNivel(e.target.value)}>
              <option value="">Todos</option>
              <option value="CRITICO">Crítico</option>
              <option value="EN_RIESGO">En riesgo</option>
              <option value="ACEPTABLE">Aceptable</option>
            </select>
          </label>
          <label className="field">
            <span>Alerta</span>
            <select className="select" value={regla} onChange={(e) => setRegla(e.target.value)}>
              <option value="">Todas</option>
              <option value="R1_NOTA_CRITICA">Nota crítica</option>
              <option value="R2_DESCENSO">Descenso sostenido</option>
              <option value="ninguna">Sin alerta</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={conIncidencias} onChange={(e) => setConIncidencias(e.target.checked)} />
            Con incidencias
          </label>
          <button className="btn btn-sm" onClick={limpiar} style={{ marginLeft: 'auto' }}>
            Limpiar filtros
          </button>
        </div>

      </section>

      {/* Cuadrícula minimalista: cabecera única y celdas con divisores finos (semántica de tabla para lectores de pantalla) */}
      <div className="cuadricula-estudiantes stagger-2" role="table" aria-label="Estudiantes del curso">
        <div className="cuadricula-fila cuadricula-cabecera" role="row">
          {['Estudiante', 'Exámenes', 'Tareas', 'APE', 'Promedio', 'Nivel', 'Tendencia', 'Incidencias', 'Alerta'].map((t) => (
            <div key={t} role="columnheader">
              {t}
            </div>
          ))}
        </div>
        {filas.map(({ e, m, estados }) => {
          const criticas = [
            estados.cero > 0 ? plural(estados.cero, 'nota cero', 'notas cero') : null,
            estados.sin_entrega > 0 ? `${estados.sin_entrega} sin entrega` : null,
          ].filter(Boolean);
          return (
            <div
              key={e.id_number}
              role="row"
              className="cuadricula-fila"
              data-testid="fila-estudiante"
              onClick={() => navegar(`/estudiantes/${e.id_number}`)}
            >
              <div role="cell" className="celda-estudiante">
                <Link to={`/estudiantes/${e.id_number}`} onClick={(ev) => ev.stopPropagation()}>
                  {e.nombres}
                </Link>
                <span data-testid="datos-estudiante">
                  {e.cedula ? `C.I. ${e.cedula}` : 'C.I. —'} · {e.email}
                </span>
              </div>
              <div role="cell" className="num">{nota(m?.acd)}</div>
              <div role="cell" className="num">{nota(m?.tareas)}</div>
              <div role="cell" className="num">{nota(m?.pae)}</div>
              <div role="cell" className="num celda-promedio">{nota(m?.nota_final)}</div>
              <div role="cell">{m ? <NivelBadge nivel={m.nivel_riesgo} /> : <span className="muted small">Sin notas</span>}</div>
              <div role="cell">{m ? <Tendencia m={m} /> : <span className="muted small">Sin datos</span>}</div>
              <div role="cell" className="celda-incidencias" data-testid="incidencias">
                {criticas.length > 0 && <span className="incidencias-criticas">{criticas.join(' · ')}</span>}
                {estados.pendiente > 0 && <span className="pendientes-compacto">{estados.pendiente} sin calificar</span>}
                {criticas.length === 0 && estados.pendiente === 0 && <span className="pendientes-compacto">Sin incidencias</span>}
              </div>
              <div role="cell">
                {e.regla_alerta ? (
                  <span className={`badge ${e.regla_alerta.startsWith('R1') ? 'nivel-critico' : 'nivel-riesgo'}`}>
                    {REGLAS[e.regla_alerta] ?? e.regla_alerta}
                  </span>
                ) : (
                  <span className="sin-alertas">Sin alertas</span>
                )}
              </div>
            </div>
          );
        })}
        {filas.length === 0 && <p className="muted est-vacio">Ningún estudiante coincide con la búsqueda.</p>}
      </div>
      <p className="small muted est-conteo">
        Mostrando {filas.length} de {datos!.estudiantes.length} estudiantes.
      </p>
    </>
  );
}
