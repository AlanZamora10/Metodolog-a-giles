/** Historial del chat del agente (RF-09): se conserva al navegar y se borra al cerrar sesión. */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { ApiError } from '../api/client';
import { endpoints } from '../api/endpoints';
import type { ChatResponse } from '../api/types';

export interface MensajeChat {
  id: string;
  rol: 'docente' | 'agente' | 'error';
  texto: string;
  fecha: string;
  cursoId?: number | null;
  detalle?: ChatResponse;
}

interface ChatValor {
  mensajes: MensajeChat[];
  enviando: boolean;
  enviar: (texto: string, cursoId: number | null) => Promise<void>;
  limpiar: () => void;
}

const ChatContext = createContext<ChatValor | null>(null);
const CLAVE = 'edumonitor.chat';
let contador = 0;
const nuevoId = () => `${Date.now()}-${++contador}`;

export function ChatProvider({ children }: { children: ReactNode }) {
  const [mensajes, setMensajes] = useState<MensajeChat[]>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(CLAVE) ?? '[]');
    } catch {
      return [];
    }
  });
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    try {
      sessionStorage.setItem(CLAVE, JSON.stringify(mensajes.slice(-60)));
    } catch {
      /* sin almacenamiento */
    }
  }, [mensajes]);

  const enviar = useCallback(async (texto: string, cursoId: number | null) => {
    const limpio = texto.trim();
    if (!limpio) return;
    setMensajes((m) => [...m, { id: nuevoId(), rol: 'docente', texto: limpio, fecha: new Date().toISOString(), cursoId }]);
    setEnviando(true);
    try {
      const r = await endpoints.chat(limpio, cursoId);
      setMensajes((m) => [
        ...m,
        { id: nuevoId(), rol: 'agente', texto: r.respuesta, fecha: new Date().toISOString(), cursoId, detalle: r },
      ]);
    } catch (ex) {
      const texto = ex instanceof ApiError ? `No se pudo consultar al agente (${ex.status || 'red'}): ${ex.detail}` : 'No se pudo consultar al agente.';
      setMensajes((m) => [...m, { id: nuevoId(), rol: 'error', texto, fecha: new Date().toISOString() }]);
    } finally {
      setEnviando(false);
    }
  }, []);

  const limpiar = useCallback(() => setMensajes([]), []);

  return <ChatContext.Provider value={{ mensajes, enviando, enviar, limpiar }}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatValor {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat debe usarse dentro de <ChatProvider>');
  return ctx;
}
