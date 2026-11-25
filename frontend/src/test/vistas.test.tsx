import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
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
    expect(screen.getByText('1 estudiante aprobado')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\(s\)/);
  });

  it('leyenda de referencias en la cabecera y pestañas por tipo de actividad', async () => {
    iniciarSesionFalsa();
    mockApi();
    const u = userEvent.setup();
    renderApp('/dashboard');
    await screen.findByText('6.05');
    expect(screen.getAllByTestId('leyenda-referencias')).toHaveLength(3);   // unidad, actividad y componentes
    expect(screen.getAllByTestId('leyenda-referencias')[0]).toHaveTextContent(/Aprobación \(7\.00\).*Crítico \(5\.00\)/);
    expect(screen.getByTestId('leyenda-codigos')).toHaveTextContent('A = Examen');
    const grafico = () => screen.getByRole('img', { name: /U1-A1|U1-T2|U2-T4/ });
    expect(grafico().getAttribute('aria-label')).toMatch(/U1-A1.*U1-T2/);
    await u.click(screen.getByRole('tab', { name: 'Exámenes (A)' }));
    expect(screen.getByRole('tab', { name: 'Exámenes (A)' })).toHaveAttribute('aria-selected', 'true');
    expect(grafico().getAttribute('aria-label')).not.toMatch(/U1-T2/);
    await u.click(screen.getByRole('tab', { name: 'Tareas (T)' }));
    expect(grafico().getAttribute('aria-label')).not.toMatch(/U1-A1/);
    await u.click(screen.getByRole('tab', { name: 'Prácticas APE (P)' }));
    expect(screen.getByText('Sin actividades calificadas de este tipo en el corte.')).toBeInTheDocument();
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
    // Cabecera ordenada: C.I. · correo · materia y paralelo
    const meta = screen.getByTestId('perfil-meta');
    expect([...meta.querySelectorAll('span')].map((s) => s.textContent)).toEqual([
      'C.I. 1804923199',
      'u-04@uta.edu.ec',
      'Programación orientada a objetos — Paralelo A',
    ]);
    // Calificaciones agrupadas por parcial y tipo: evaluaciones, prácticas APE y tareas (en orden de unidad)
    const parcial = screen.getByTestId('parcial-1');
    expect(within(parcial).getByRole('columnheader', { name: 'Primer Parcial' })).toBeInTheDocument();
    const filas = [...parcial.querySelectorAll('tr')].map((tr) => tr.textContent ?? '');
    const indice = (texto: string) => filas.findIndex((f) => f.includes(texto));
    expect(indice('Evaluaciones')).toBeLessThan(indice('U1-A1'));
    expect(indice('U1-A1')).toBeLessThan(indice('Prácticas APE'));
    expect(indice('Prácticas APE')).toBeLessThan(indice('U2-P1'));
    expect(indice('U2-P1')).toBeLessThan(indice('Tareas'));
    expect(indice('U1-T2')).toBeLessThan(indice('U2-T4'));
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
    expect(screen.getByText(/julio a diciembre 2026/i, { selector: 'td' })).toBeInTheDocument();
    // Documento sobrio institucional, sin textos aclaratorios de la herramienta
    expect(screen.getByText('UNIVERSIDAD TÉCNICA DE AMBATO')).toBeInTheDocument();
    expect(document.querySelector('.informe-oficial img.informe-escudo')).toHaveAttribute('src', '/uta-escudo-azul.png');
    expect(screen.queryByText(/determinista|calculado a partir|señales para revisión|sin texto inventado/i)).not.toBeInTheDocument();
    expect(document.querySelector('.informe-oficial .badge, .informe-oficial .metricas-mini')).toBeNull();
    expect(screen.getByText('Atender primero las alertas de nota crítica.')).toBeInTheDocument();
    // 4. Hallazgos en 3 sub-bloques ordenados y 5. Recomendaciones numeradas por prioridad
    expect(screen.getByTestId('hallazgos-1')).toHaveTextContent('4.1. Rendimiento general del curso');
    expect(screen.getByTestId('hallazgos-2')).toHaveTextContent('4.2. Estudiantes que requieren atención');
    expect(screen.getByTestId('hallazgos-3')).toHaveTextContent('4.3. Componentes y entregas pendientes');
    const recomendaciones = screen.getByTestId('recomendaciones');
    expect(recomendaciones.tagName).toBe('OL');
    expect(within(recomendaciones).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Atender primero las alertas de nota crítica.',
      'Calificación de pendientes: calificar la actividad pendiente y volver a sincronizar para completar el análisis.',
    ]);
    expect(document.querySelector('.informe-oficial')?.textContent).not.toMatch(/\(s\)|\(es\)/);

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
    await u.click(await screen.findByRole('button', { name: 'Microsoft Office 365' }));
    await u.type(await screen.findByLabelText(/correo institucional/i), 'rgomez');
    await u.type(screen.getByLabelText(/contraseña/i), 'RobertoGomez1!');
    await u.click(screen.getByRole('button', { name: 'Ingresar' }));
    expect(await screen.findByTestId('login-error')).toHaveTextContent(/correo institucional completo/i);
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/auth/login'))).toBe(false);
  });
});
