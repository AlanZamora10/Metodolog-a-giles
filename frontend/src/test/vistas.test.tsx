import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { REPORTE, iniciarSesionFalsa, json, mockApi, renderApp } from './helpers';

describe('RF-03 / RF-04 / RNF-08 · cursos, período y sincronización', () => {
  it('muestra selector de curso, período académico y el origen/fecha de la última sincronización', async () => {
    iniciarSesionFalsa();
    mockApi();
    renderApp('/dashboard');
    expect(await screen.findByRole('heading', { name: 'SOF-POO-A' })).toBeInTheDocument();
    expect(screen.getByLabelText('Curso')).toHaveDisplayValue(/SOF-POO-A/);
    expect(screen.getByLabelText('Período académico')).toHaveDisplayValue('Julio a Diciembre 2026 (2026-JD)');
    expect(screen.getByText(/origen: restaurado desde sql server/i)).toBeInTheDocument();
  });

  it('el botón Sincronizar llama a POST /api/sincronizacion y actualiza el origen', async () => {
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
    await screen.findByRole('heading', { name: 'SOF-POO-A' });
    await userEvent.click(screen.getByRole('button', { name: /sincronizar/i }));
    expect(await screen.findByText(/origen: moodle uta 4\.3\.2/i)).toBeInTheDocument();
    expect(fetch.mock.calls.some(([u, i]) => u === '/api/sincronizacion' && i?.method === 'POST')).toBe(true);
  });

  it('el buscador y los filtros reducen el listado de estudiantes', async () => {
    iniciarSesionFalsa();
    mockApi();
    const u = userEvent.setup();
    renderApp('/estudiantes');
    await screen.findByText('Diego Curillo');
    await u.type(screen.getByPlaceholderText(/nombre, código/i), 'valeria');
    expect(screen.queryByText('Diego Curillo')).not.toBeInTheDocument();
    expect(screen.getByText('Valeria Ortiz')).toBeInTheDocument();
    await u.clear(screen.getByPlaceholderText(/nombre, código/i));
    await u.click(screen.getByLabelText(/con incidencias/i));
    expect(screen.getByText('Diego Curillo')).toBeInTheDocument();
    expect(screen.queryByText('Camila Andrade')).not.toBeInTheDocument();
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
    expect(await screen.findByRole('heading', { name: 'Diego Curillo' })).toBeInTheDocument();
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

    expect(await screen.findByRole('heading', { name: /informe académico — sof-poo-a/i })).toBeInTheDocument();
    expect(screen.getByText(/julio a diciembre 2026/i, { selector: 'dd' })).toBeInTheDocument();
    expect(screen.getByText('Atender primero las alertas R1.')).toBeInTheDocument();

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
