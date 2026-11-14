import type { ReactNode } from 'react';
import { useCurso } from '../../context/CursoContext';
import { Aviso, Esqueleto, Vacio } from '../ui/ui';

/** Muestra el contenido sólo cuando hay un curso con datos cargados; si no, guía al docente. */
export function CursoRequerido({ children }: { children: ReactNode }) {
  const c = useCurso();
  if (c.estadoSync === 'cargando' || (c.cargandoCurso && !c.datos)) {
    return (
      <div className="grid" aria-busy="true">
        <Esqueleto alto={110} />
        <Esqueleto alto={280} />
      </div>
    );
  }
  if (!c.sync?.cursos.length) {
    return (
      <div className="card">
        <Vacio titulo="Aún no hay cursos sincronizados desde Moodle UTA">
          <p>Sincronice para traer sus cursos, estudiantes y calificaciones.</p>
          <button className="btn btn-primary" onClick={() => c.sincronizar()} disabled={c.estadoSync === 'sincronizando'}>
            Sincronizar ahora
          </button>
        </Vacio>
      </div>
    );
  }
  if (c.errorCurso) {
    return (
      <Aviso tipo="error">
        <div>
          <strong>No se pudieron cargar los datos del curso.</strong> {c.errorCurso}{' '}
          <button className="btn-link" onClick={c.recargarCurso}>
            Reintentar
          </button>
        </div>
      </Aviso>
    );
  }
  if (!c.datos) return null;
  return <>{children}</>;
}
