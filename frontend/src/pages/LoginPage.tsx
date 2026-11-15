import { useState, type FormEvent } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { mensajeErrorLogin, useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';
import { Aviso } from '../components/ui/ui';
import { URL_RECUPERAR_CLAVE } from '../utils/config';

/** Correo institucional completo: usuario + 4 últimos dígitos de la cédula @uta.edu.ec */
export const CORREO_UTA = /^[a-z0-9._%+-]+@uta\.edu\.ec$/i;

/** Inicio de sesión con el correo institucional de Moodle UTA. */
export function LoginPage() {
  const { usuario, iniciarSesion, aviso } = useAuth();
  const location = useLocation();
  const [correo, setCorreo] = useState('');
  const [password, setPassword] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<{ texto: string; estado: number } | null>(null);

  if (usuario) {
    const destino = (location.state as { desde?: string } | null)?.desde ?? '/dashboard';
    return <Navigate to={destino} replace />;
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const limpio = correo.trim();
    if (!limpio || !password) {
      setError({ texto: 'Ingrese su correo institucional y su contraseña.', estado: 0 });
      return;
    }
    if (!CORREO_UTA.test(limpio)) {
      setError({ texto: 'Ingrese su correo institucional completo (por ejemplo, usuario1234@uta.edu.ec).', estado: 422 });
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await iniciarSesion(limpio, password);
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
        <div className="brand login-brand stagger-1" style={{ borderBottom: 'none', padding: 0 }}>
          <img src="/uta-escudo-blanco.png" alt="" aria-hidden className="login-escudo" />
          <div>
            <div className="brand-name">EduMonitor AI</div>
            <div className="brand-sub">Universidad Técnica de Ambato · FISEI</div>
          </div>
        </div>
        <h1 className="stagger-2">Seguimiento académico inteligente para sus cursos de Moodle UTA</h1>
        <p className="login-pie stagger-3">Facultad de Ingeniería en Sistemas, Electrónica e Industrial · Período Julio–Diciembre 2026</p>
      </section>

      <section className="login-form-wrap">
        <form className="login-form" onSubmit={enviar} noValidate>
          <div className="stagger-1">
            <img src="/uta-logo-azul.png" alt="Universidad Técnica de Ambato" className="login-logo" />
            <h1 style={{ marginTop: 18 }}>Iniciar sesión</h1>
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

          <label className="field stagger-2">
            <span>Correo institucional</span>
            <input
              className="input"
              type="email"
              name="email"
              autoComplete="username"
              inputMode="email"
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              disabled={enviando}
              autoFocus
            />
          </label>
          <label className="field stagger-3">
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
          <button className="btn btn-primary stagger-4" type="submit" disabled={enviando}>
            {enviando && <span className="spinner" aria-hidden />}
            {enviando ? 'Validando con Moodle UTA…' : 'Ingresar'}
          </button>
          <div className="login-ayuda stagger-5">
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
