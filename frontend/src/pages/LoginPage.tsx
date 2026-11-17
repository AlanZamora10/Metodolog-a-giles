import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { mensajeErrorLogin, useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';
import { Aviso } from '../components/ui/ui';
import { URL_RECUPERAR_CLAVE } from '../utils/config';

/** Correo institucional completo: usuario + 4 últimos dígitos de la cédula @uta.edu.ec */
export const CORREO_UTA = /^[a-z0-9._%+-]+@uta\.edu\.ec$/i;

/** Logotipo de Microsoft (cuatro cuadros) para el botón de acceso institucional. */
function IconoMicrosoft() {
  return (
    <svg width="20" height="20" viewBox="0 0 21 21" aria-hidden focusable="false">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  );
}

/**
 * Inicio de sesión institucional (flujo tipo «Microsoft Office 365» de la Plataforma Educativa UTA):
 * 1) tarjeta con el escudo y el botón Microsoft Office 365; 2) al pulsarlo se despliega el formulario de
 * credenciales de Moodle UTA (correo @uta.edu.ec y contraseña), con opción para volver.
 */
export function LoginPage() {
  const { usuario, iniciarSesion, aviso } = useAuth();
  const location = useLocation();
  const [paso, setPaso] = useState<'inicio' | 'credenciales'>('inicio');
  const [correo, setCorreo] = useState('');
  const [password, setPassword] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<{ texto: string; estado: number } | null>(null);
  const botonO365 = useRef<HTMLButtonElement>(null);
  const volvio = useRef(false);

  useEffect(() => {
    // Al volver de las credenciales, el foco regresa al botón de Microsoft Office 365
    if (paso === 'inicio' && volvio.current) botonO365.current?.focus();
  }, [paso]);

  if (usuario) {
    const destino = (location.state as { desde?: string } | null)?.desde ?? '/dashboard';
    return <Navigate to={destino} replace />;
  }

  function volver() {
    volvio.current = true;
    setError(null);
    setPassword('');
    setPaso('inicio');
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
    <div className="login-page login-institucional">
      <main className="login-tarjeta stagger-1">
        <div className="login-escudos">
          <img src="/uta-logo-azul.png" alt="Universidad Técnica de Ambato" className="login-logo" />
          <span className="login-sello" aria-label="Facultad de Ingeniería en Sistemas, Electrónica e Industrial">
            FISEI
          </span>
        </div>
        <h1 className="login-titulo">EduMonitor AI · Sistema de Monitoreo Académico</h1>

        {aviso && !error && <Aviso tipo="warn">{aviso}</Aviso>}

        {paso === 'inicio' ? (
          <section className="login-paso fade-up" key="inicio" aria-label="Opciones de acceso">
            <p className="login-sub">Identifíquese usando su cuenta en:</p>
            <button
              ref={botonO365}
              type="button"
              className="btn-o365"
              aria-expanded={false}
              aria-controls="login-credenciales"
              onClick={() => setPaso('credenciales')}
            >
              <IconoMicrosoft />
              Microsoft Office 365
            </button>
          </section>
        ) : (
          <form
            id="login-credenciales"
            className="login-form login-paso fade-up"
            key="credenciales"
            onSubmit={enviar}
            noValidate
            aria-label="Credenciales institucionales"
          >
            <p className="login-sub login-sub-o365">
              <IconoMicrosoft />
              <span>Ingrese con sus credenciales institucionales de Moodle UTA</span>
            </p>

            {error && (
              <Aviso tipo={error.estado === 503 || error.estado === 0 ? 'warn' : 'error'}>
                <span data-testid="login-error">{error.texto}</span>
              </Aviso>
            )}

            <label className="field">
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
            <button type="button" className="login-volver" onClick={volver} disabled={enviando}>
              ← Volver a las opciones de acceso
            </button>
          </form>
        )}

        <p className="login-pie">Facultad de Ingeniería en Sistemas, Electrónica e Industrial · Período Julio–Diciembre 2026</p>
      </main>
    </div>
  );
}
