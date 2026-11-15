import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { REPORTE, iniciarSesionFalsa, json, mockApi, renderApp } from './helpers';

describe('RF-03 / RF-04 / RNF-08 · cursos, período y sincronización', () => {
  it('selectores limpios (materia y paralelo, período sin código) y fecha de la última sincronización', async () => {
    iniciarSesionFalsa();
    mockApi();
    renderApp('/dashboard');
    expect(await screen.findByRole('heading', { name: 'Programación orientada a objetos — Paralelo A' })).toBeInTheDocument();
    expect(screen.getByLabelText('Curso')).toHaveDisplayValue('Programación orientada a objetos — Paralelo A');
    expect(screen.getByLabelText('Período académico')).toHaveDisplayValue('Julio a Diciembre 2026');
    expect(screen.getByLabelText('Corte de evaluación')).toHaveDisplayValue('Período completo');
    expect(screen.getByText(/sincronizado hace/i)).toBeInTheDocument();
    for (const tecnico of [/SOF-POO-A/, /2026-JD/, /origen/i, /SQL Server/, /RF-\d/, /U1–U2/]) {
      expect(document.body.textContent).not.toMatch(tecnico);
    }
  });

  it('el botón Sincronizar llama a POST /api/sincronizacion y actualiza la fecha', async () => {
    iniciarSesionFalsa();
    const fetch = mockApi({
      'POST /api/sincronizacion': () =>
        json({
          status: 'success', duracion_ms: 900,
          ultima_sincronizacion: new Date().toISOString(),
          moodle: { sitio: 'Moodle UTA', version: '4.3.2 (Build: 20231222)' },
          persistencia: { motor: 'mssql' },
          total_cursos: 1, total_estudiantes: 3, estudiantes: [],
          cursos: [{ id: 2, shortname: 'SOF-POO-A', fullname: 'POO', total_estudiantes: 3, promedio: 6, criticos: 1, en_riesgo: 1, aceptables: 1, alertas_r1: 1, alertas_r2: 0 }],
        }),
    });
    renderApp('/dashboard');
    await screen.findByRole('heading', { name: 'Programación orientada a objetos — Paralelo A' });
    await userEvent.click(screen.getByRole('button', { name: /sincronizar/i }));
    expect(await screen.findByText(/sincronizado hace instantes/i)).toBeInTheDocument();
    expect(fetch.mock.calls.some(([u, i]) => u === '/api/sincronizacion' && i?.method === 'POST')).toBe(true);
  });

  it('el buscador y los filtros reducen el listado de estudiantes', async () => {
    iniciarSesionFalsa();
    mockApi();
    const u = userEvent.setup();
    renderApp('/estudiantes');
    await screen.findByText('Carlos Andrés Mendoza Paredes');
    await u.type(screen.getByPlaceholderText(/cédula o nombre completo/i), 'valeria');
    expect(screen.queryByText('Carlos Andrés Mendoza Paredes')).not.toBeInTheDocument();
    expect(screen.getByText('Valeria Sofía Ortiz Zambrano')).toBeInTheDocument();
    await u.clear(screen.getByPlaceholderText(/cédula o nombre completo/i));
    await u.click(screen.getByLabelText(/con incidencias/i));
    expect(screen.getByText('Carlos Andrés Mendoza Paredes')).toBeInTheDocument();
    expect(screen.queryByText('Camila Alejandra Andrade Morales')).not.toBeInTheDocument();
  });
});

describe('RF-05 · dashboard', () => {
  it('KPIs con escala /10, tasa de aprobación y alertas activas', async () => {
    iniciarSesionFalsa();
    mockApi();
    renderApp('/dashboard');
    expect(await screen.findByText('6.05')).toBeInTheDocument();
    expect(screen.getByText('/10')).toBeInTheDocument();
    expect(screen.getByText('33.3')).toBeInTheDocument();
    expect(screen.getByText('Alertas activas').parentElement).toHaveTextContent('2');
  });
});

describe('RF-06 · ficha del estudiante', () => {
  it('diferencia calificada, nota cero, sin entrega y pendiente', async () => {
    iniciarSesionFalsa();
    mockApi();
    renderApp('/estudiantes/U-04');
    expect(await screen.findByRole('heading', { name: 'Carlos Andrés Mendoza Paredes' })).toBeInTheDocument();
    for (const estado of ['calificada', 'cero', 'sin_entrega', 'pendiente']) {
      expect(document.querySelector(`.tabla [data-estado="${estado}"]`)).not.toBeNull();
    }
    expect(screen.getByTestId('estado-cero')).toHaveTextContent('1');
    expect(screen.getAllByText('Nota cero (0.0)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Pendiente de calificación').length).toBeGreaterThan(0);
  });
});

describe('RF-11 · informe', () => {
  it('muestra la vista previa y descarga el .md con el JWT', async () => {
    const token = iniciarSesionFalsa();
    const fetch = mockApi({
      'GET /api/v1/courses/2/reporte': (_i, url) =>
        url.includes('formato=md')
          ? new Response('# Informe', { headers: { 'Content-Disposition': 'attachment; filename="informe_SOF-POO-A.md"' } })
          : json(REPORTE),
    });
    const crear = vi.fn(() => 'blob:informe');
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: crear, revokeObjectURL: vi.fn() }));
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const u = userEvent.setup();
    renderApp('/reporte');

    expect(await screen.findByRole('heading', { name: /informe académico — programación orientada a objetos — paralelo a/i })).toBeInTheDocument();
    expect(screen.getByText(/julio a diciembre 2026/i, { selector: 'dd' })).toBeInTheDocument();
    expect(screen.getByText('Atender primero las alertas de nota crítica.')).toBeInTheDocument();

    await u.click(screen.getByRole('button', { name: /descargar \.md/i }));
    await waitFor(() => expect(clic).toHaveBeenCalled());
    const [, init] = fetch.mock.calls.find(([url]) => String(url).includes('formato=md'))!;
    expect((init!.headers as Record<string, string>).Authorization).toBe(`Bearer ${token}`);
    expect(crear).toHaveBeenCalled();
  });

  it('Imprimir / guardar PDF usa la impresión del navegador', async () => {
    iniciarSesionFalsa();
    mockApi();
    const imprimir = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    renderApp('/reporte');
    await userEvent.click(await screen.findByRole('button', { name: /imprimir/i }));
    expect(imprimir).toHaveBeenCalled();
  });
});

describe('Buscador por cédula y nombre completo', () => {
  it('filtra en tiempo real por cédula (completa o parcial) y por nombre completo, mostrando cédula y correo', async () => {
    iniciarSesionFalsa();
    mockApi();
    const u = userEvent.setup();
    renderApp('/estudiantes');
    await screen.findByText('Carlos Andrés Mendoza Paredes');
    expect(screen.getByText('Carlos Andrés Mendoza Paredes').closest('td')).toHaveTextContent('C.I. 1804923199 · u-04@uta.edu.ec');

    const buscar = screen.getByPlaceholderText(/cédula o nombre completo/i);
    await u.type(buscar, '1804923199');
    expect(screen.getByText('Carlos Andrés Mendoza Paredes')).toBeInTheDocument();
    expect(screen.queryByText('Valeria Sofía Ortiz Zambrano')).not.toBeInTheDocument();

    await u.clear(buscar);
    await u.type(buscar, '17045');
    expect(screen.getByText('Valeria Sofía Ortiz Zambrano')).toBeInTheDocument();
    expect(screen.queryByText('Carlos Andrés Mendoza Paredes')).not.toBeInTheDocument();

    await u.clear(buscar);
    await u.type(buscar, 'camila andrade');
    expect(screen.getByText('Camila Alejandra Andrade Morales')).toBeInTheDocument();
    expect(screen.getAllByTestId('datos-estudiante')).toHaveLength(1);

    // Mientras se escribe: inicio de cada palabra de los dos nombres y dos apellidos
    await u.clear(buscar);
    await u.type(buscar, 'mendoza par');
    expect(screen.getByText('Carlos Andrés Mendoza Paredes')).toBeInTheDocument();
    expect(screen.getAllByTestId('datos-estudiante')).toHaveLength(1);
  });
});

describe('Login con correo institucional', () => {
  it('rechaza el nombre de usuario sin llamar al servidor', async () => {
    const fetch = mockApi();
    const u = userEvent.setup();
    renderApp('/login');
    await u.type(await screen.findByLabelText(/correo institucional/i), 'rgomez');
    await u.type(screen.getByLabelText(/contraseña/i), 'Docente2026!');
    await u.click(screen.getByRole('button', { name: 'Ingresar' }));
    expect(await screen.findByTestId('login-error')).toHaveTextContent(/correo institucional completo/i);
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/auth/login'))).toBe(false);
  });
});
