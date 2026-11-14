import { describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DOCENTE, iniciarSesionFalsa, json, mockApi, renderApp, tokenFalso } from './helpers';

async function intentarLogin(usuario = 'rgomez@uta.edu.ec', clave = 'Docente2026!') {
  const u = userEvent.setup();
  await u.type(screen.getByLabelText(/correo o usuario/i), usuario);
  await u.type(screen.getByLabelText(/contraseña/i), clave);
  await u.click(screen.getByRole('button', { name: /ingresar/i }));
}

describe('RF-01 · Login con Moodle UTA', () => {
  it.each([
    [401, 'Credenciales inválidas.', /credenciales inválidas/i],
    [403, 'El usuario no es docente de ningún curso SOF-.', /no es docente/i],
    [503, 'No se pudo validar con Moodle UTA: timeout', /moodle uta no responde/i],
  ])('muestra un mensaje claro para HTTP %i', async (status, detail, esperado) => {
    mockApi({ 'POST /api/v1/auth/login': () => json({ detail }, status) });
    renderApp('/login');
    await intentarLogin();
    expect(await screen.findByTestId('login-error')).toHaveTextContent(esperado);
    expect(sessionStorage.getItem('edumonitor.sesion')).toBeNull();
  });

  it('envía correo o usuario en el campo email y guarda el JWT con su vencimiento', async () => {
    const token = tokenFalso(120);
    const fetch = mockApi({ 'POST /api/v1/auth/login': () => json({ access_token: token, token_type: 'bearer', user: DOCENTE }) });
    renderApp('/login');
    await intentarLogin('  rgomez  ');
    expect(await screen.findByRole('heading', { name: 'SOF-POO-A' })).toBeInTheDocument();

    const [, init] = fetch.mock.calls.find(([u]) => String(u).endsWith('/auth/login'))!;
    expect(JSON.parse(String(init!.body))).toEqual({ email: 'rgomez', password: 'Docente2026!' });
    const sesion = JSON.parse(sessionStorage.getItem('edumonitor.sesion')!);
    expect(sesion.token).toBe(token);
    expect(sesion.expira).toBeGreaterThan(Date.now() + 119 * 60_000);
    // Las peticiones posteriores llevan el Bearer
    const conAuth = fetch.mock.calls.find(([u]) => String(u) === '/api/sincronizacion');
    expect((conAuth![1]!.headers as Record<string, string>).Authorization).toBe(`Bearer ${token}`);
  });

  it('sin sesión, una ruta protegida redirige al login', async () => {
    mockApi();
    renderApp('/alertas');
    expect(await screen.findByRole('heading', { name: /iniciar sesión/i })).toBeInTheDocument();
  });

  it('un 401 con sesión activa cierra la sesión automáticamente y avisa', async () => {
    iniciarSesionFalsa();
    mockApi({ 'GET /api/sincronizacion': () => json({ detail: 'Token inválido o expirado.' }, 401) });
    renderApp('/dashboard');
    expect(await screen.findByText(/su sesión expiró o ya no es válida/i)).toBeInTheDocument();
    await waitFor(() => expect(sessionStorage.getItem('edumonitor.sesion')).toBeNull());
  });
});
