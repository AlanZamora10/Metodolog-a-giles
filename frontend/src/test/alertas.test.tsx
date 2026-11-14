import { describe, expect, it } from 'vitest';
import { screen, waitFor, within, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ALERTAS, diferido, iniciarSesionFalsa, json, mockApi, renderApp } from './helpers';

function respuestaAtender(alertaId: number, nombre: string) {
  const alerta = { ...ALERTAS.find((a) => a.id === alertaId)!, estado: 'ATENDIDA' };
  return {
    status: 'success',
    mensaje: 'ok',
    alerta,
    refuerzo: {
      id: 100 + alertaId, alerta_id: alertaId, titulo: `Refuerzo para ${nombre}`, descripcion: null,
      instrucciones: `Instrucciones para ${nombre}`, actividades: [], origen: 'MOTOR_HEURISTICO_HU11B',
      estado: 'BORRADOR', cmid: null, moodle_url: null,
    },
    diagnostico: {},
  };
}

describe('RF-07 / RF-10 · Centro de alertas', () => {
  it('muestra la evidencia numérica de cada alerta', async () => {
    iniciarSesionFalsa();
    mockApi();
    renderApp('/alertas');
    const item = await screen.findByTestId('alerta-1');
    expect(item).toHaveTextContent('3.04');
    expect(item).toHaveTextContent('-0.25');
    expect(item).toHaveTextContent('R1 · nota ponderada < 5.00');
    expect(item).not.toHaveTextContent(/reprobad/i);
  });

  it('el panel cambia al instante al estudiante elegido y descarta la respuesta tardía de la alerta anterior', async () => {
    iniciarSesionFalsa();
    const lento = diferido<Response>();
    mockApi({
      'POST /api/v1/alertas/1/atender': () => lento.promesa,
      'POST /api/v1/alertas/2/atender': () => json(respuestaAtender(2, 'Valeria Ortiz')),
    });
    const u = userEvent.setup();
    renderApp('/alertas');

    // 1) Atender a Diego: el panel muestra a Diego sin esperar al backend
    await u.click(within(await screen.findByTestId('alerta-1')).getByRole('button', { name: 'Atender' }));
    expect(screen.getByTestId('panel-destinatario')).toHaveTextContent('Diego Curillo');
    expect(screen.getByDisplayValue(/Diego Curillo <u-04@uta.edu.ec>/)).toBeInTheDocument();

    // 2) Antes de que responda, el docente atiende a Valeria: el panel cambia de inmediato
    await u.click(within(screen.getByTestId('alerta-2')).getByRole('button', { name: 'Atender' }));
    expect(screen.getByTestId('panel-destinatario')).toHaveTextContent('Valeria Ortiz');
    expect(await screen.findByDisplayValue('Instrucciones para Valeria Ortiz')).toBeInTheDocument();

    // 3) Llega tarde la respuesta de Diego: se ignora
    await act(async () => lento.resolver(json(respuestaAtender(1, 'Diego Curillo'))));
    expect(screen.getByTestId('panel-destinatario')).toHaveTextContent('Valeria Ortiz');
    expect(screen.queryByDisplayValue('Instrucciones para Diego Curillo')).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('Instrucciones para Valeria Ortiz')).toBeInTheDocument();
  });

  it('aprueba con confirmación explícita, envía la recomendación editada y muestra el cmid real', async () => {
    iniciarSesionFalsa();
    const fetch = mockApi({
      'POST /api/v1/alertas/2/atender': () => json(respuestaAtender(2, 'Valeria Ortiz')),
      'POST /api/v1/refuerzos/102/publicar': () =>
        json({
          status: 'success', mensaje: 'ok', cmid: 165, moodle_link: 'http://localhost:8080/mod/assign/view.php?id=165',
          fecha_entrega: '2026-11-20T23:59:00-05:00', refuerzo: { id: 102 },
        }),
    });
    const u = userEvent.setup();
    renderApp('/alertas');
    await u.click(within(await screen.findByTestId('alerta-2')).getByRole('button', { name: 'Atender' }));
    const instr = await screen.findByDisplayValue('Instrucciones para Valeria Ortiz');
    await u.clear(instr);
    await u.type(instr, 'Resolver la guía de herencia y polimorfismo.');

    await u.click(screen.getByRole('button', { name: 'Aprobar y publicar en Moodle' }));
    const dialogo = screen.getByRole('dialog');
    expect(dialogo).toHaveTextContent('sólo para Valeria Ortiz');
    await u.click(within(dialogo).getByRole('button', { name: 'Aprobar y publicar' }));

    const ok = await screen.findByTestId('publicado');
    expect(ok).toHaveTextContent('165');
    expect(within(ok).getByRole('link', { name: /abrir tarea en moodle/i })).toHaveAttribute(
      'href',
      'http://localhost:8080/mod/assign/view.php?id=165',
    );
    const [, init] = fetch.mock.calls.find(([url]) => String(url).endsWith('/refuerzos/102/publicar'))!;
    const body = JSON.parse(String(init!.body));
    expect(body.confirmado).toBe(true);
    expect(body.instrucciones).toBe('Resolver la guía de herencia y polimorfismo.');
    expect(body.fecha_entrega).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('si Moodle falla (502) informa sin marcar la alerta como publicada', async () => {
    iniciarSesionFalsa();
    mockApi({
      'POST /api/v1/alertas/1/atender': () => json(respuestaAtender(1, 'Diego Curillo')),
      'POST /api/v1/refuerzos/101/publicar': () => json({ detail: 'Moodle no creó la tarea: timeout' }, 502),
    });
    const u = userEvent.setup();
    renderApp('/alertas');
    await u.click(within(await screen.findByTestId('alerta-1')).getByRole('button', { name: 'Atender' }));
    await screen.findByDisplayValue('Instrucciones para Diego Curillo');
    await u.click(screen.getByRole('button', { name: 'Aprobar y publicar en Moodle' }));
    await u.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Aprobar y publicar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/la alerta no cambió de estado/i);
    await waitFor(() => expect(screen.queryByTestId('publicado')).not.toBeInTheDocument());
  });
});
