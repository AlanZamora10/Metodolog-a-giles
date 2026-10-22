#!/usr/bin/env python3
"""
==============================================================================
CAPA INTELIGENTE DE SEGUIMIENTO ACADÉMICO PARA MOODLE (FISEI - UTA)
Script de Simulación y Carga de Curso de Prueba (HU-01)
Responsables: Justin Ojeda (Backend) & Johan Borja (Arquitectura & DB)
==============================================================================

Criterio de Aceptación HU-01 (Gherkin):
  Dado que existe una instancia de Moodle en contenedor o la BD analítica
  Cuando el administrador ejecuta la carga del curso simulado
  Entonces el curso contiene 2 materias, 7 estudiantes, 2 parciales y 4 unidades
  (categorías de calificación "Unidad 1" a "Unidad 4"), cada actividad tiene un ID
  number normalizado [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA] y al menos 2 estudiantes
  tienen nota ponderada menor a 5.0 (casos críticos).

Fórmula oficial UTA:
  Nota Final = (0.40 * Autónomo) + (0.30 * Tareas) + (0.30 * PAE)
==============================================================================
"""

import sys
import os
import json
import argparse
from typing import Dict, List, Any

# Estructura del curso simulado HU-01
COURSE_DATA: Dict[str, Any] = {
    "materias": [
        {
            "codigo": "MAT1",
            "nombre": "Metodologías Ágiles",
            "carrera": "Ingeniería de Software - FISEI",
            "docente": "Ing. Hernán Naranjo, Mg.",
            "creditos": 3
        },
        {
            "codigo": "MAT2",
            "nombre": "Ingeniería de Software",
            "carrera": "Ingeniería de Software - FISEI",
            "docente": "Ing. Hernán Naranjo, Mg.",
            "creditos": 3
        }
    ],
    "periodos": [
        {
            "codigo": "2026-B",
            "nombre": "Ciclo Académico Octubre 2026 - Febrero 2027",
            "parciales": [
                {"numero": 1, "nombre": "Parcial 1"},
                {"numero": 2, "nombre": "Parcial 2"}
            ]
        }
    ],
    "unidades": [
        {"numero": 1, "nombre": "Unidad 1", "titulo": "Fundamentos y Conceptos"},
        {"numero": 2, "nombre": "Unidad 2", "titulo": "Lógica y Modelado (Punto Crítico)"},
        {"numero": 3, "nombre": "Unidad 3", "titulo": "Estructuras Aplicadas"},
        {"numero": 4, "nombre": "Unidad 4", "titulo": "Arquitectura e Integración"}
    ],
    "estudiantes": [
        {"id_number": "U-03", "nombres": "Estudiante A", "email": "estudiante.a@uta.edu.ec"},
        {"id_number": "U-04", "nombres": "Estudiante B", "email": "estudiante.b@uta.edu.ec"},
        {"id_number": "U-05", "nombres": "Estudiante C", "email": "estudiante.c@uta.edu.ec"}, # Caso Crítico (<5.0)
        {"id_number": "U-06", "nombres": "Estudiante D", "email": "estudiante.d@uta.edu.ec"}, # Caso Crítico (<5.0)
        {"id_number": "U-07", "nombres": "Estudiante E", "email": "estudiante.e@uta.edu.ec"},
        {"id_number": "U-08", "nombres": "Estudiante F", "email": "estudiante.f@uta.edu.ec"}, # En Riesgo (5.0 a 6.9)
        {"id_number": "U-09", "nombres": "Estudiante G", "email": "estudiante.g@uta.edu.ec"}
    ],
    "actividades_mat1_p1": [
        {
            "id_number": "MAT1-P1-U1-T1",
            "nombre": "Taller de Fundamentos Ágiles",
            "unidad": "Unidad 1",
            "tema": "Tema 1.1",
            "componente": "AUTONOMO",
            "ponderacion": 0.40
        },
        {
            "id_number": "MAT1-P1-U2-T2",
            "nombre": "Evaluación Teórica de Modelado",
            "unidad": "Unidad 2",
            "tema": "Tema 2.1",
            "componente": "AUTONOMO",
            "ponderacion": 0.40
        },
        {
            "id_number": "MAT1-P1-U2-T3",
            "nombre": "Diagramación y Algoritmos Reutilizables",
            "unidad": "Unidad 2",
            "tema": "Tema 2.3",
            "componente": "TAREAS",
            "ponderacion": 0.30
        },
        {
            "id_number": "MAT1-P1-U3-T4",
            "nombre": "Desglose de Historias y Criterios Gherkin",
            "unidad": "Unidad 3",
            "tema": "Tema 3.1",
            "componente": "TAREAS",
            "ponderacion": 0.30
        },
        {
            "id_number": "MAT1-P1-U4-T5",
            "nombre": "Laboratorio PAE: Entorno Base y CI/CD",
            "unidad": "Unidad 4",
            "tema": "Tema 4.1",
            "componente": "PAE",
            "ponderacion": 0.30
        }
    ],
    # Calificaciones ponderadas precalculadas conforme fórmula oficial UTA
    "calificaciones_estudiantes": [
        {
            "id_number": "U-03",
            "nombres": "Estudiante A",
            "autonomo": 8.00,
            "tareas": 8.00,
            "pae": 8.00,
            "notas_detalle": {"MAT1-P1-U1-T1": 8.0, "MAT1-P1-U2-T2": 8.0, "MAT1-P1-U2-T3": 8.0, "MAT1-P1-U3-T4": 8.0, "MAT1-P1-U4-T5": 8.0}
        },
        {
            "id_number": "U-04",
            "nombres": "Estudiante B",
            "autonomo": 8.50,
            "tareas": 8.50,
            "pae": 8.50,
            "notas_detalle": {"MAT1-P1-U1-T1": 8.5, "MAT1-P1-U2-T2": 8.5, "MAT1-P1-U2-T3": 8.5, "MAT1-P1-U3-T4": 8.5, "MAT1-P1-U4-T5": 8.5}
        },
        {
            # CASO CRÍTICO 1 (< 5.0)
            "id_number": "U-05",
            "nombres": "Estudiante C",
            "autonomo": 3.50,
            "tareas": 3.00,
            "pae": 4.00,
            "notas_detalle": {"MAT1-P1-U1-T1": 6.0, "MAT1-P1-U2-T2": 2.0, "MAT1-P1-U2-T3": 2.0, "MAT1-P1-U3-T4": 4.0, "MAT1-P1-U4-T5": 4.0}
        },
        {
            # CASO CRÍTICO 2 (< 5.0)
            "id_number": "U-06",
            "nombres": "Estudiante D",
            "autonomo": 4.50,
            "tareas": 4.00,
            "pae": 5.00,
            "notas_detalle": {"MAT1-P1-U1-T1": 3.5, "MAT1-P1-U2-T2": 5.5, "MAT1-P1-U2-T3": 4.0, "MAT1-P1-U3-T4": 4.0, "MAT1-P1-U4-T5": 5.0}
        },
        {
            "id_number": "U-07",
            "nombres": "Estudiante E",
            "autonomo": 8.00,
            "tareas": 7.00,
            "pae": 7.67,
            "notas_detalle": {"MAT1-P1-U1-T1": 8.0, "MAT1-P1-U2-T2": 8.0, "MAT1-P1-U2-T3": 7.0, "MAT1-P1-U3-T4": 7.0, "MAT1-P1-U4-T5": 7.6}
        },
        {
            # EN RIESGO (5.0 a 6.9)
            "id_number": "U-08",
            "nombres": "Estudiante F",
            "autonomo": 6.50,
            "tareas": 6.00,
            "pae": 6.00,
            "notas_detalle": {"MAT1-P1-U1-T1": 7.0, "MAT1-P1-U2-T2": 6.0, "MAT1-P1-U2-T3": 6.0, "MAT1-P1-U3-T4": 6.0, "MAT1-P1-U4-T5": 6.0}
        },
        {
            "id_number": "U-09",
            "nombres": "Estudiante G",
            "autonomo": 8.50,
            "tareas": 8.00,
            "pae": 8.70,
            "notas_detalle": {"MAT1-P1-U1-T1": 8.5, "MAT1-P1-U2-T2": 8.5, "MAT1-P1-U2-T3": 8.0, "MAT1-P1-U3-T4": 8.0, "MAT1-P1-U4-T5": 8.7}
        }
    ]
}


def calcular_nota_ponderada(autonomo: float, tareas: float, pae: float) -> float:
    """Calcula la nota ponderada oficial: 40% Autónomo + 30% Tareas + 30% PAE."""
    nota = (0.40 * autonomo) + (0.30 * tareas) + (0.30 * pae)
    return round(nota, 2)


def clasificar_nivel(nota: float) -> str:
    """Clasifica al alumno según los umbrales institucionales."""
    if nota < 5.0:
        return "CRITICO"
    elif nota < 7.0:
        return "EN_RIESGO"
    return "ACEPTABLE"


def validar_criterios_hu01() -> Dict[str, Any]:
    """Valida los criterios de aceptación formales de HU-01."""
    materias_count = len(COURSE_DATA["materias"])
    estudiantes_count = len(COURSE_DATA["estudiantes"])
    unidades_count = len(COURSE_DATA["unidades"])
    parciales_count = len(COURSE_DATA["periodos"][0]["parciales"])

    # Validar IDs normalizados
    id_format_errors = []
    for act in COURSE_DATA["actividades_mat1_p1"]:
        partes = act["id_number"].split("-")
        if len(partes) != 4 or not (partes[0].startswith("MAT") and partes[1].startswith("P") and partes[2].startswith("U") and partes[3].startswith("T")):
            id_format_errors.append(act["id_number"])

    # Calcular y clasificar notas
    evaluaciones = []
    casos_criticos = 0
    casos_en_riesgo = 0
    casos_aceptables = 0

    for est in COURSE_DATA["calificaciones_estudiantes"]:
        final = calcular_nota_ponderada(est["autonomo"], est["tareas"], est["pae"])
        nivel = clasificar_nivel(final)
        if nivel == "CRITICO":
            casos_criticos += 1
        elif nivel == "EN_RIESGO":
            casos_en_riesgo += 1
        else:
            casos_aceptables += 1

        evaluaciones.append({
            "id_number": est["id_number"],
            "nombres": est["nombres"],
            "autonomo": est["autonomo"],
            "tareas": est["tareas"],
            "pae": est["pae"],
            "nota_final": final,
            "nivel": nivel
        })

    criterio_materias = (materias_count == 2)
    criterio_estudiantes = (estudiantes_count == 7)
    criterio_unidades = (unidades_count == 4)
    criterio_parciales = (parciales_count == 2)
    criterio_ids = (len(id_format_errors) == 0)
    criterio_criticos = (casos_criticos >= 2)

    aprobado = all([
        criterio_materias,
        criterio_estudiantes,
        criterio_unidades,
        criterio_parciales,
        criterio_ids,
        criterio_criticos
    ])

    return {
        "aprobado": aprobado,
        "materias": materias_count,
        "estudiantes": estudiantes_count,
        "unidades": unidades_count,
        "parciales": parciales_count,
        "casos_criticos": casos_criticos,
        "casos_en_riesgo": casos_en_riesgo,
        "casos_aceptables": casos_aceptables,
        "errores_id": id_format_errors,
        "evaluaciones": evaluaciones
    }


def imprimir_resumen(resultado: Dict[str, Any]):
    print("=" * 78)
    print("  FISEI - UTA | CAPA INTELIGENTE DE SEGUIMIENTO ACADÉMICO PARA MOODLE")
    print("  VERIFICACIÓN DE HU-01: CURSO SIMULADO EN MOODLE")
    print("=" * 78)
    print(f"Materias simuladas          : {resultado['materias']} (Requerido: 2) -> {'OK' if resultado['materias']==2 else 'FAIL'}")
    print(f"Estudiantes de prueba        : {resultado['estudiantes']} (U-03 a U-09) -> {'OK' if resultado['estudiantes']==7 else 'FAIL'}")
    print(f"Parciales por periodo        : {resultado['parciales']} (Parcial 1, 2)  -> {'OK' if resultado['parciales']==2 else 'FAIL'}")
    print(f"Categorías de Unidad        : {resultado['unidades']} (Unidad 1 a 4)   -> {'OK' if resultado['unidades']==4 else 'FAIL'}")
    print(f"Convención ID normalizado    : {len(COURSE_DATA['actividades_mat1_p1'])} actividades válidas -> {'OK' if not resultado['errores_id'] else 'FAIL'}")
    print(f"Estudiantes Críticos (< 5.0) : {resultado['casos_criticos']} (Requerido: >= 2) -> {'OK' if resultado['casos_criticos']>=2 else 'FAIL'}")
    print("-" * 78)
    print(f"{'ID':<8} {'Nombre':<16} {'Autón. (40%)':<14} {'Tareas (30%)':<14} {'PAE (30%)':<12} {'Final':<8} {'Nivel'}")
    print("-" * 78)
    for ev in resultado["evaluaciones"]:
        flag = "[CRITICO]" if ev["nivel"] == "CRITICO" else ("[RIESGO]" if ev["nivel"] == "EN_RIESGO" else "[OK]")
        print(f"{ev['id_number']:<8} {ev['nombres']:<16} {ev['autonomo']:<14.2f} {ev['tareas']:<14.2f} {ev['pae']:<12.2f} {ev['nota_final']:<8.2f} {flag} {ev['nivel']}")
    print("=" * 78)
    if resultado["aprobado"]:
        print("  RESULTADO: HU-01 CUMPLE TODOS LOS CRITERIOS DE ACEPTACIÓN")
    else:
        print("  RESULTADO: FALLO EN CRITERIOS DE ACEPTACIÓN")
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(description="Simulación y validación de HU-01")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON estructurado")
    parser.add_argument("--export", type=str, help="Exportar datos a archivo JSON")
    args = parser.parse_args()

    resultado = validar_criterios_hu01()

    if args.export:
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(COURSE_DATA, f, indent=2, ensure_ascii=False)
        print(f"Datos exportados a: {args.export}")

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        imprimir_resumen(resultado)

    sys.exit(0 if resultado["aprobado"] else 1)


if __name__ == "__main__":
    main()
