from app.services.id_parser import IDNumberParser


def test_valid_id_number_parsing():
    """
    Verifica que IDs conformes a [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA] se extraigan correctamente.
    """
    parsed = IDNumberParser.parse("MAT1-P1-U2-T3")
    assert parsed["valido"] is True
    assert parsed["estado"] == "clasificado"
    assert parsed["materia"] == "MAT1"
    assert parsed["parcial"] == 1
    assert parsed["unidad"] == 2
    assert parsed["tema"] == "Tema 3"
    assert parsed["unidad_nombre"] == "Unidad 2"


def test_id_number_case_insensitivity():
    """
    Verifica que el parser soporte minúsculas sin alterar la clasificación.
    """
    parsed = IDNumberParser.parse("mat2-p2-u4-t1")
    assert parsed["valido"] is True
    assert parsed["materia"] == "MAT2"
    assert parsed["parcial"] == 2
    assert parsed["unidad"] == 4


def test_invalid_id_number_categorized_as_sin_clasificar():
    """
    Verifica que IDs no normalizados se cataloguen como 'sin_clasificar' (HU-04, HU-16).
    """
    parsed_invalid = IDNumberParser.parse("TAREA_EXTRA_FINAL")
    assert parsed_invalid["valido"] is False
    assert parsed_invalid["estado"] == "sin_clasificar"

    parsed_none = IDNumberParser.parse(None)
    assert parsed_none["valido"] is False
    assert parsed_none["estado"] == "sin_clasificar"
