import { useState, type FormEvent } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { mensajeErrorLogin, useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';
import { Aviso } from '../components/ui/ui';

/** RF-01: inicio de sesión con la cuenta de Moodle UTA (correo o usuario). */
export function LoginPage() {
  const { usuario, iniciarSesion, aviso } = useAuth();
  const location = useLocation();
  const [identificador, setIdentificador] = useState('');
  const [password, setPassword] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<{ texto: string; estado: number } | null>(null);

  if (usuario) {
    const destino = (location.state as { desde?: string } | null)?.desde ?? '/dashboard';
    return <Navigate to={destino} replace />;
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!identificador.trim() || !password) {
      setError({ texto: 'Ingrese su correo o usuario de Moodle y su contraseña.', estado: 0 });
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await iniciarSesion(identificador, password);
    } catch (ex) {
      setError({ texto: mensajeErrorLogin(ex), estado: ex instanceof ApiError ? ex.status : 0 });
      setPassword('');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-hero">
        <div className="brand" style={{ borderBottom: 'none', padding: 0 }}>
          <div className="brand-logo" aria-hidden>
            EM
          </div>
          <div>
            <div className="brand-name">EduMonitor AI</div>
            <div className="brand-sub">Universidad Técnica de Ambato · FISEI</div>
          </div>
        </div>
        <div>
          <h1>Seguimiento académico inteligente para sus cursos de Moodle UTA</h1>
          <p>Sincronice calificaciones, detecte estudiantes en riesgo y publique refuerzos personalizados con apoyo del agente de IA.</p>
          <ul>
            <li>Alertas tempranas con evidencia numérica</li>
            <li>Refuerzos visibles sólo para el estudiante en Moodle</li>
            <li>Informe del curso descargable</li>
          </ul>
        </div>
        <p className="small" style={{ opacity: 0.6 }}>
          Carrera de Ingeniería de Software · Período Julio–Diciembre 2026
        </p>
      </section>

      <section className="login-form-wrap">
        <form className="login-form" onSubmit={enviar} noValidate>
          <div>
            <h1>Iniciar sesión</h1>
            <p className="muted" style={{ marginTop: 6 }}>
              Use la misma cuenta con la que ingresa a Moodle UTA. Sólo docentes de los cursos de Software.
            </p>
          </div>

          {aviso && !error && <Aviso tipo="warn">{aviso}</Aviso>}
          {error && (
            <Aviso tipo={error.estado === 503 || error.estado === 0 ? 'warn' : 'error'}>
              <div>
                <span data-testid="login-error">{error.texto}</span>
                {error.estado === 503 && (
                  <div className="small" style={{ marginTop: 4 }}>
                    El inicio de sesión se valida directamente con Moodle; no hay credenciales locales de respaldo.
                  </div>
                )}
              </div>
            </Aviso>
          )}

          <label className="field">
            <span>Correo o usuario de Moodle UTA</span>
            <input
              className="input"
              type="text"
              autoComplete="username"
              placeholder="rgomez@uta.edu.ec"
              value={identificador}
              onChange={(e) => setIdentificador(e.target.value)}
              disabled={enviando}
              autoFocus
            />
          </label>
          <label className="field">
            <span>Contraseña</span>
            <input
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={enviando}
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={enviando}>
            {enviando && <span className="spinner" aria-hidden />}
            {enviando ? 'Validando con Moodle UTA…' : 'Ingresar'}
          </button>
          <p className="small muted">La sesión se guarda sólo en esta pestaña y se cierra automáticamente al vencer.</p>
        </form>
      </section>
    </div>
  );
}
