import { describe, expect, it } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ALERTAS, iniciarSesionFalsa, json, mockApi, renderApp } from './helpers';
import { Markdown } from '../components/ui/Markdown';

const RESPUESTA_ALERTAS = {
  respuesta:
    '**Resumen ejecutivo**\n- Hay **2 alerta(s) activa(s)**; 2 siguen abiertas.\n\n### Alertas tempranas\n' +
    '- **Diego Curillo** (SOF-POO-A) · R1 nota crítica · nota **3.04/10**\n  - Incidencias: U2-T4 (sin entrega)\n' +
    '- **Valeria Ortiz** (SOF-POO-A) · R1 nota crítica · nota **4.07/10**',
  formato: 'markdown',
  herramientas: [
    { herramienta: 'listar_cursos_autorizados', parametros: {}, resultado: { filas: 4 }, duracion_ms: 3 },
    { herramienta: 'identificar_alertas', parametros: { course_id: 2 }, resultado: { filas: 2, alertas: [] }, duracion_ms: 5 },
  ],
  plan_fuente: 'ollama_slm+reglas',
  redaccion: 'determinista_desde_herramientas',
  duracion_ms: 7400,
};

const RESPUESTA_REFUERZO = {
  respuesta: 'Preparé una propuesta de refuerzo para **Diego Curillo** en **SOF-POO-A**.\n\n**Título:** Refuerzo Unidad 2 — SOF-POO-A',
  formato: 'markdown',
  herramientas: [
    {
      herramienta: 'proponer_refuerzo',
      parametros: { student_query: 'Diego Curillo', course_id: 2 },
      duracion_ms: 4,
      resultado: {
        filas: 1,
        estudiante: { id_number: 'U-04', nombres: 'Diego Curillo' },
        curso: 'SOF-POO-A',
        curso_id: 2,
        propuesta: {
          titulo: 'Refuerzo Unidad 2: Informe de laboratorio — SOF-POO-A',
          objetivo: 'Que Diego Curillo consolide la Unidad 2',
          pasos: ['Revise U1-T2'],
          criterios: [{ criterio: 'Corrección técnica', peso: 100 }],
          plazo_dias: 7,
          instrucciones: 'Objetivo: Que Diego Curillo consolide la Unidad 2\n\nDescripción de la tarea:\n1. Revise U1-T2',
        },
        alerta: { id: 1, estado: 'ABIERTA', regla: 'R1_NOTA_CRITICA' },
      },
    },
  ],
  plan_fuente: 'reglas_deterministas',
  redaccion: 'determinista_desde_herramientas',
  duracion_ms: 120,
};

describe('RF-09 · respuestas estructuradas del agente', () => {
  it('renderiza Markdown seguro: títulos, viñetas anidadas, listas numeradas y negritas', () => {
    render(<Markdown texto={'**Resumen**\n- uno **dos**\n  - hijo\n\n### Sección\n1. paso <script>x</script>'} />);
    expect(screen.getByText('Resumen').tagName).toBe('STRONG');
    expect(screen.getByText('dos').tagName).toBe('STRONG');
    expect(screen.getByText('hijo').closest('ul')?.parentElement?.tagName).toBe('LI');
    expect(screen.getByRole('heading', { name: 'Sección' })).toBeInTheDocument();
    expect(screen.getByText('paso <script>x</script>').tagName).toBe('LI'); // el HTML se muestra como texto
    expect(document.querySelector('script')).toBeNull();
  });

  it('muestra la respuesta formateada, sugerencias por categoría y contexto activo, sin la tarjeta técnica de herramientas', async () => {
    iniciarSesionFalsa();
    const fetch = mockApi({ 'POST /api/v1/agent/chat': () => json(RESPUESTA_ALERTAS) });
    const u = userEvent.setup();
    renderApp('/agente');
    await screen.findByRole('heading', { name: 'Agente IA' });
    await waitFor(() => expect(screen.getByLabelText('Curso')).toHaveDisplayValue(/SOF-POO-A/));

    expect(screen.queryByText(/herramientas disponibles/i)).not.toBeInTheDocument();
    expect(screen.queryByText('listar_cursos_autorizados')).not.toBeInTheDocument();
    for (const g of ['Panorama general', 'Seguimiento de estudiantes', 'Actividades', 'Intervención']) {
      expect(screen.getByText(g)).toBeInTheDocument();
    }
    expect(within(screen.getByLabelText('Contexto activo')).getByText('SOF-POO-A')).toBeInTheDocument();

    await u.click(screen.getByRole('button', { name: '¿Qué estudiantes de SOF-POO-A necesitan atención?' }));
    expect(await screen.findByRole('heading', { name: 'Alertas tempranas' })).toBeInTheDocument();
    expect(screen.getByText('Diego Curillo', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('Incidencias: U2-T4 (sin entrega)')).toBeInTheDocument();
    const [, init] = fetch.mock.calls.find(([url]) => url === '/api/v1/agent/chat')!;
    expect(JSON.parse(String(init!.body))).toEqual({ mensaje: '¿Qué estudiantes de SOF-POO-A necesitan atención?', course_id: 2 });
  });

  it('RF-12: auditoría colapsada con nombres amigables y tiempo; JSON sólo al expandir', async () => {
    iniciarSesionFalsa();
    mockApi({ 'POST /api/v1/agent/chat': () => json(RESPUESTA_ALERTAS) });
    const u = userEvent.setup();
    renderApp('/agente');
    await u.type(await screen.findByLabelText('Mensaje para el agente'), 'alertas de POO{enter}');

    const auditoria = await screen.findByTestId('auditoria');
    expect(auditoria).not.toHaveAttribute('open');
    const resumen = within(auditoria).getByText(/Cursos autorizados del docente · Alertas tempranas · 7\.4 s/);
    expect(resumen).toBeVisible();
    expect(within(auditoria).getByText('Auditoría y fuentes consultadas (RF-12)')).toBeInTheDocument();

    await u.click(within(auditoria).getByText('Auditoría y fuentes consultadas (RF-12)'));
    expect(auditoria).toHaveAttribute('open');
    const fuentes = within(auditoria).getAllByTestId('herramienta-usada');
    expect(fuentes).toHaveLength(2);
    const detalle = fuentes[1].querySelector('details')!;
    expect(detalle).not.toHaveAttribute('open');
    await u.click(within(fuentes[1]).getByText('Ver parámetros y registros'));
    expect(detalle).toHaveAttribute('open');
    expect(fuentes[1]).toHaveTextContent('"course_id": 2');
    expect(fuentes[1]).toHaveTextContent('identificar_alertas');
  });

  it('la propuesta de refuerzo se aplica en el Centro de alertas conservando el texto del agente', async () => {
    iniciarSesionFalsa();
    const fetch = mockApi({
      'POST /api/v1/agent/chat': () => json(RESPUESTA_REFUERZO),
      'POST /api/v1/alertas/1/atender': () =>
        json({
          status: 'success',
          mensaje: 'ok',
          alerta: { ...ALERTAS[0], estado: 'ATENDIDA', refuerzo_id: 101 },
          refuerzo: { id: 101, alerta_id: 1, titulo: 'Texto del motor', instrucciones: 'Texto del motor', estado: 'BORRADOR', origen: 'X' },
          diagnostico: {},
        }),
    });
    const u = userEvent.setup();
    renderApp('/agente');
    await u.type(await screen.findByLabelText('Mensaje para el agente'), 'Prepárame un refuerzo para Diego Curillo{enter}');
    await u.click(await screen.findByRole('button', { name: 'Aplicar en el Centro de alertas' }));

    expect(await screen.findByTestId('propuesta-agente')).toBeInTheDocument();
    expect(screen.getByTestId('panel-destinatario')).toHaveTextContent('Diego Curillo');
    expect(screen.getByDisplayValue('Refuerzo Unidad 2: Informe de laboratorio — SOF-POO-A')).toBeInTheDocument();

    await u.click(screen.getByRole('button', { name: 'Registrar atención' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Aprobar y publicar en Moodle' })).toBeEnabled());
    expect(fetch.mock.calls.some(([url]) => url === '/api/v1/alertas/1/atender')).toBe(true);
    // El texto del agente no se reemplaza por el del motor heurístico
    expect(screen.getByDisplayValue('Refuerzo Unidad 2: Informe de laboratorio — SOF-POO-A')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Texto del motor')).not.toBeInTheDocument();
  });
});

describe('RF-01 · login minimalista', () => {
  it('campos vacíos sin placeholder, enlace de recuperación a Moodle y sin texto técnico', async () => {
    mockApi();
    renderApp('/login');
    const usuario = await screen.findByLabelText(/correo o usuario/i);
    const clave = screen.getByLabelText(/contraseña/i);
    expect(usuario).toHaveValue('');
    expect(clave).toHaveValue('');
    expect(usuario).not.toHaveAttribute('placeholder');
    expect(clave).not.toHaveAttribute('placeholder');
    expect(screen.getByText('Ingrese con sus credenciales institucionales de Moodle UTA')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '¿Olvidó su contraseña?' })).toHaveAttribute(
      'href',
      'http://localhost:8080/login/forgot_password.php',
    );
    expect(screen.getByText('La contraseña se gestiona en Moodle UTA.')).toBeInTheDocument();
    expect(screen.getByText(/Facultad de Ingeniería en Sistemas, Electrónica e Industrial · Período Julio–Diciembre 2026/)).toBeInTheDocument();
    expect(screen.queryByText(/sessionStorage|sólo en esta pestaña/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Carrera de Ingeniería de Software/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Alertas tempranas con evidencia/)).not.toBeInTheDocument();
  });
});
