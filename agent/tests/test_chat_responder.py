"""Respuesta abierta con datos reales (RAG): Ollama redacta sólo con los datos que envía el middleware."""

import asyncio
import json

import httpx

from app import chat_responder

DATOS = "CURSO: POO — Paralelo A | estudiantes: 2\n- Carlos Mendoza | 3.50 | 2.81 | 3.88 | 3.41 | crítico | al alza"


def _mock(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(chat_responder.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_envia_datos_y_prompt_estricto_y_devuelve_la_redaccion(monkeypatch):
    capturado = {}

    def handler(request):
        capturado["json"] = json.loads(request.read().decode("utf-8"))
        return httpx.Response(200, json={"message": {"role": "assistant",
                                                     "content": "**Carlos Mendoza** tiene **3.41/10** (crítico)."}})

    _mock(monkeypatch, handler)
    r = asyncio.run(chat_responder.responder("¿quién va peor en POO?", DATOS, "es"))
    assert r == {"respuesta": "**Carlos Mendoza** tiene **3.41/10** (crítico).", "fuente": "ollama_rag"}
    sistema, usuario = capturado["json"]["messages"]
    assert "EXCLUSIVAMENTE" in sistema["content"] and "No inventes" in sistema["content"]
    assert usuario["content"].startswith("DATOS:\nCURSO: POO") and usuario["content"].endswith("PREGUNTA: ¿quién va peor en POO?")
    assert capturado["json"]["options"]["temperature"] == 0 and capturado["json"]["stream"] is False


def test_prompt_en_ingles(monkeypatch):
    capturado = {}

    def handler(request):
        capturado["json"] = json.loads(request.read().decode("utf-8"))
        return httpx.Response(200, json={"message": {"content": "ok"}})

    _mock(monkeypatch, handler)
    asyncio.run(chat_responder.responder("who is failing?", DATOS, "en"))
    assert "ONLY the DATA" in capturado["json"]["messages"][0]["content"]


def test_sin_ollama_o_sin_datos_no_responde(monkeypatch):
    monkeypatch.setattr(chat_responder, "OLLAMA_HOST", "http://127.0.0.1:9")
    monkeypatch.setattr(chat_responder, "RAG_TIMEOUT", 1.0)
    assert asyncio.run(chat_responder.responder("¿quién va peor?", DATOS)) == {"respuesta": None,
                                                                            "fuente": "sin_respuesta_llm"}
    assert asyncio.run(chat_responder.responder("¿quién va peor?", "")) == {"respuesta": None,
                                                                         "fuente": "sin_respuesta_llm"}
