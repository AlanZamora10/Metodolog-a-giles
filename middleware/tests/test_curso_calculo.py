"""
Curso Cálculo (Telecomunicaciones, SOF-CAL-A): sólo registra aportes de Tareas (Tarea 1-3).

- La ponderación 40/30/30 se aplica sobre los componentes que el curso ya evaluó: sin Exámenes ni APE la nota es
  el promedio de las tareas (no 0.3 x tareas).
- Los cursos con los tres componentes conservan exactamente la fórmula oficial.
- Sigla, nombre con tilde y contenidos de refuerzo de las 2 unidades del documento del curso.
"""

import pytest

from app.services import agente_herramientas, contenidos_academicos, sync_service

ESTUDIANTE = {"fullname": "Ariana Nicole Pazmiño Ríos", "roles": [{"shortname": "student"}]}

# APORTES del documento: Estudiante N -> (Tarea 1, Tarea 2, Tarea 3)
APORTES = {1: (1.5, 1.5, 4.0), 2: (7.0, 1.5, 8.0), 3: (1.5, 8.0, 1.5), 4: (3.0, 8.0, 9.0), 5: (7.0, 6.0, 8.0),
           6: (4.0, 6.0, 5.0), 7: (1.7, 9.0, 3.0), 8: (4.0, 1.5, 1.5), 9: (7.0, 9.0, 1.5), 10: (8.7, 8.8, 9.0)}


def _gi(idnumber, raw=None, feedback=""):
    return {"idnumber": idnumber, "itemname": idnumber, "graderaw": raw, "grademax": 10, "feedback": feedback}


def _items(t1, t2, t3):
    return [_gi("U1-T1", t1), _gi("U1-T2", t2), _gi("U2-T3", t3)]


def _curso_calculo():
    usuarios = [{"id": 1, "fullname": "Docente", "email": "d@uta.edu.ec", "roles": [{"shortname": "editingteacher"}]}]
    usuarios += [{**ESTUDIANTE, "id": 100 + n, "idnumber": f"U-{28 + n}"} for n in APORTES]
    grades = {100 + n: _items(*notas) for n, notas in APORTES.items()}
    return sync_service._construir_curso(
        {"id": 9, "shortname": "SOF-CAL-A", "fullname": "(TEL) CALCULO - A"}, usuarios, grades)


@pytest.mark.parametrize("n", sorted(APORTES))
def test_nota_de_calculo_es_el_promedio_de_sus_tareas(n):
    est = {e["id_number"]: e for e in _curso_calculo()["estudiantes"]}[f"U-{28 + n}"]
    esperado = round(sum(APORTES[n]) / 3, 2)
    assert est["tareas"] == esperado and est["acd"] is None and est["pae"] is None
    assert est["nota_final"] == esperado


def test_niveles_y_tendencia_de_calculo():
    est = {e["id_number"]: e for e in _curso_calculo()["estudiantes"]}
    assert est["U-38"]["nota_final"] == 8.83 and est["U-38"]["nivel_riesgo"] == "ACEPTABLE"   # Estudiante 10
    assert est["U-36"]["nota_final"] == 2.33 and est["U-36"]["nivel_riesgo"] == "CRITICO"     # Estudiante 8
    assert est["U-34"]["nota_final"] == 5.0 and est["U-34"]["nivel_riesgo"] == "EN_RIESGO"    # Estudiante 6
    # U1 = promedio(T1, T2), U2 = T3: Estudiante 9 baja de 8.00 a 1.50
    assert est["U-37"]["promedios_unidad"] == {"U1": 8.0, "U2": 1.5}
    assert est["U-37"]["por_parcial"][1]["nota_final"] == est["U-37"]["nota_final"]


def test_cursos_con_los_tres_componentes_no_cambian():
    items = [_gi("U1-A1", 3.0), _gi("U1-T1", 4.0), _gi("U1-T2", 0.0), _gi("U1-P1", 3.5)]
    evaluados = sync_service.componentes_evaluados([items])
    assert evaluados[None] == {"ACD", "TAREAS", "PAE"}
    e = sync_service.construir_estudiante({"id": 1, "idnumber": "U-04"}, items, evaluados)
    assert e["nota_final"] == 2.85   # 0.4*3.0 + 0.3*2.0 + 0.3*3.5


def test_componente_evaluado_por_el_curso_sigue_aportando_cero():
    # El curso evaluó Exámenes (a otro estudiante); a éste sólo le quedó pendiente: su ACD aporta 0.00
    otro = [_gi("U1-A1", 9.0), _gi("U1-T1", 8.0)]
    propio = [_gi("U1-A1", None, "PENDIENTE DE REVISIÓN"), _gi("U1-T1", 8.0)]
    evaluados = sync_service.componentes_evaluados([otro, propio])
    assert evaluados[None] == {"ACD", "TAREAS"}
    e = sync_service.construir_estudiante({"id": 2, "idnumber": "U-05"}, propio, evaluados)
    assert e["nota_final"] == round(0.3 * 8.0 / 0.7, 2)


def test_nota_ponderada_sin_evaluados_es_la_formula_oficial():
    promedios = {"ACD": None, "TAREAS": 8.0, "PAE": None}
    assert sync_service.nota_ponderada(promedios) == 2.4
    assert sync_service.nota_ponderada(promedios, {"TAREAS"}) == 8.0


def test_nombre_sigla_y_contenidos_de_calculo():
    assert agente_herramientas._nombre_curso("(TEL) CALCULO - A") == "Cálculo, paralelo A"
    curso = {"id": 9, "shortname": "SOF-CAL-A", "fullname": "(TEL) CALCULO - A"}
    otro = {"id": 2, "shortname": "SOF-POO-A", "fullname": "(SOF) PROGRAMACION ORIENTADA A OBJETOS - A"}
    for texto in ("como va calculo", "notas de cal", "quien va mejor en calculo"):
        assert agente_herramientas._curso_mencionado(texto, [otro, curso]) == 9
    assert contenidos_academicos.contenido_unidad("SOF-CAL-A", 1)["titulo"] == "Derivada"
    assert contenidos_academicos.contenido_unidad("SOF-CAL-A", 2)["titulo"] == "Integral indefinida"
    assert contenidos_academicos.objetivo_unidad("SOF-CAL-A", 2)
    assert "GeoGebra" in contenidos_academicos.entorno_materia("SOF-CAL-A")
