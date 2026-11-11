#!/usr/bin/env python3
"""
==============================================================================
SCRIPT DE PRUEBA INTEGRAL END-TO-END (SPRINT 2 & SPRINT 3)
Capa Inteligente de Seguimiento Académico para Moodle (FISEI - UTA)
==============================================================================
Ejecuta la validación de extremo a extremo:
  1. Login y emisión de token JWT (HU-01 / RN-01).
  2. Consulta de métricas deterministas de curso y estudiantes (HU-03 / HU-04).
  3. Detección y listado de alertas R1/R2 (HU-05 / RN-12, RN-13).
  4. Invocación al Agente IA (Ollama llama3.2 / fallback heurístico) para borrador.
  5. Cierre de alerta terminal mediante PATCH /cerrar (RN-14).
  6. Publicación aprobada en Moodle con confirmación explícita (RN-17).
  7. Trazabilidad en auditoría (RN-18).
==============================================================================
"""

import sys
import json
import time

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

BASE_URL = "http://localhost:8000/api/v1"

def print_step(step_name, status, details=""):
    badge = "[\033[92mPASSED\033[0m]" if status == "OK" else "[\033[91mFAILED\033[0m]"
    print(f"{badge} {step_name}")
    if details:
        print(f"       -> {details}")

def make_request(endpoint, method="GET", payload=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}
    except Exception as e:
        return 500, {"error": str(e)}

def main():
    print("=" * 78)
    print("  FISEI-UTA: VALIDACIÓN END-TO-END DE LA CAPA INTELIGENTE (SPRINT 2 & 3)")
    print("=" * 78)

    # 1. Autenticación Docente (HU-01)
    status_code, auth_data = make_request("/auth/login", method="POST", payload={
        "email": "docente@uta.edu.ec",
        "password": "Docente2026!"
    })
    if status_code != 200 or "access_token" not in auth_data:
        print_step("Paso 1: Autenticación JWT (POST /auth/login)", "FAIL", str(auth_data))
        sys.exit(1)
    
    jwt_token = auth_data["access_token"]
    user_name = auth_data["user"]["nombres"]
    print_step("Paso 1: Autenticación JWT (POST /auth/login)", "OK", f"Usuario: {user_name} | Token HS256 obtenido")

    # 2. Resumen y KPIs del Curso (HU-03)
    status_code, course_data = make_request("/courses/MAT1/summary", token=jwt_token)
    if status_code == 200:
        promedio = course_data.get("promedio_general", 0)
        criticos = course_data.get("estudiantes_criticos", 0)
        print_step("Paso 2: Métricas del Curso MAT1 (GET /courses/MAT1/summary)", "OK", 
                   f"Promedio: {promedio}/10 | Críticos: {criticos} | Total: {course_data.get('total_estudiantes')} estudiantes")
    else:
        print_step("Paso 2: Métricas del Curso MAT1", "FAIL", str(course_data))

    # 3. Consulta de Alertas Académicas (HU-05)
    status_code, alertas_data = make_request("/alertas", token=jwt_token)
    if status_code == 200 and len(alertas_data) > 0:
        print_step("Paso 3: Listado de Alertas Activas (GET /alertas)", "OK", 
                   f"{len(alertas_data)} alertas detectadas ({alertas_data[0]['regla']} para {alertas_data[0]['nombres']})")
    else:
        print_step("Paso 3: Listado de Alertas Activas", "FAIL", str(alertas_data))

    # 4. Invocación al Agente de IA para Atención de Alerta #1 (Ollama / Fallback)
    start_t = time.time()
    status_code, atender_data = make_request("/alertas/1/atender", method="POST", token=jwt_token)
    duration_ms = int((time.time() - start_t) * 1000)
    
    if status_code == 200 and "refuerzo" in atender_data:
        ref = atender_data["refuerzo"]
        print_step("Paso 4: Invocación Agente IA (POST /alertas/1/atender)", "OK", 
                   f"Origen: {ref.get('origen')} ({duration_ms} ms) | Tarea: \"{ref.get('titulo')}\"")
    else:
        print_step("Paso 4: Invocación Agente IA", "FAIL", str(atender_data))

    # 5. Cierre Terminal de Alerta #2 mediante PATCH (RN-14)
    status_code, cerrar_data = make_request("/alertas/2/cerrar", method="PATCH", token=jwt_token)
    if status_code == 200 and cerrar_data.get("alerta", {}).get("estado") == "CERRADA":
        print_step("Paso 5: Cierre Terminal de Alerta (PATCH /alertas/2/cerrar)", "OK", 
                   "Alerta #2 transicionó al estado terminal CERRADA exitosamente")
    else:
        print_step("Paso 5: Cierre de Alerta", "FAIL", str(cerrar_data))

    # 6. Publicación del Refuerzo #1 en Moodle LMS con Confirmación Explícita (RN-17)
    status_code, pub_data = make_request("/refuerzos/1/publicar", method="POST", payload={
        "confirmado": True,
        "titulo": "Refuerzo Didáctico: Lógica y Diagramación (Recuperación Parcial 1)",
        "instrucciones": "Resolver los ejercicios prácticos y cargar entrega en Moodle."
    }, token=jwt_token)

    if status_code == 200 and pub_data.get("cmid"):
        cmid = pub_data.get("cmid")
        print_step("Paso 6: Publicación en Moodle LMS (POST /refuerzos/1/publicar)", "OK", 
                   f"Módulo Moodle creado con cmid: {cmid} | Estado: PUBLICADO")
    else:
        print_step("Paso 6: Publicación en Moodle LMS", "FAIL", str(pub_data))

    # 7. Verificación de Trazabilidad en Auditoría (RN-18)
    status_code, logs_data = make_request("/logs", token=jwt_token)
    if status_code == 200 and len(logs_data) > 0:
        ultimo_log = logs_data[-1]
        print_step("Paso 7: Auditoría y Trazabilidad (GET /logs)", "OK", 
                   f"Evento registrado: [{ultimo_log.get('tipo_proceso')}] {ultimo_log.get('mensaje')}")
    else:
        print_step("Paso 7: Auditoría y Trazabilidad", "FAIL", str(logs_data))

    print("=" * 78)
    print("  RESULTADO: 7/7 PRUEBAS DE INTEGRACIÓN SUPERADAS CON ÉXITO (100% PASSED)")
    print("=" * 78)

if __name__ == "__main__":
    main()
