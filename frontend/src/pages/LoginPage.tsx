import { useState, type FormEvent } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { mensajeErrorLogin, useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';
import { Aviso } from '../components/ui/ui';
import { URL_RECUPERAR_CLAVE } from '../utils/config';

/** RF-01: inicio de sesión con la cuenta institucional de Moodle UTA (correo o usuario). */
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
        <h1>Seguimiento académico inteligente para sus cursos de Moodle UTA</h1>
        <p className="login-pie">Facultad de Ingeniería en Sistemas, Electrónica e Industrial · Período Julio–Diciembre 2026</p>
      </section>

      <section className="login-form-wrap">
        <form className="login-form" onSubmit={enviar} noValidate>
          <div>
            <h1>Iniciar sesión</h1>
            <p className="muted" style={{ marginTop: 6 }}>
              Ingrese con sus credenciales institucionales de Moodle UTA
            </p>
          </div>

          {aviso && !error && <Aviso tipo="warn">{aviso}</Aviso>}
          {error && (
            <Aviso tipo={error.estado === 503 || error.estado === 0 ? 'warn' : 'error'}>
              <span data-testid="login-error">{error.texto}</span>
            </Aviso>
          )}

          <label className="field">
            <span>Correo o usuario de Moodle UTA</span>
            <input
              className="input"
              type="text"
              name="username"
              autoComplete="username"
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
              name="password"
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
          <div className="login-ayuda">
            <a href={URL_RECUPERAR_CLAVE} target="_blank" rel="noreferrer">
              ¿Olvidó su contraseña?
            </a>
            <span className="small muted">La contraseña se gestiona en Moodle UTA.</span>
          </div>
        </form>
      </section>
    </div>
  );
}
