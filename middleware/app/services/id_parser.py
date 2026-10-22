import re
from typing import Dict, Any, Optional


class IDNumberParser:
    """
    Parser y validador de la convención de ID number normalizado en Moodle:
    Formato: [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]
    Ejemplo válido: MAT1-P1-U2-T3
    """

    ID_PATTERN = re.compile(
        r"^(?P<materia>MAT\d+|[A-Z0-9]+)-(?P<parcial>P[12])-(?P<unidad>U[1-4])-(?P<tema>T\d+)$"
    )

    @classmethod
    def parse(cls, id_number: Optional[str]) -> Dict[str, Any]:
        """
        Analiza el id_number y retorna sus componentes estructurados.
        Si no cumple la convención, retorna estado 'sin_clasificar' según HU-04 y HU-16.
        """
        if not id_number or not isinstance(id_number, str):
            return {
                "valido": False,
                "estado": "sin_clasificar",
                "id_original": id_number,
                "mensaje": "ID number ausente o nulo"
            }

        match = cls.ID_PATTERN.match(id_number.strip().upper())
        if not match:
            return {
                "valido": False,
                "estado": "sin_clasificar",
                "id_original": id_number,
                "mensaje": f"El ID '{id_number}' no cumple el formato [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]"
            }

        data = match.groupdict()
        return {
            "valido": True,
            "estado": "clasificado",
            "id_original": id_number,
            "materia": data["materia"],
            "parcial": int(data["parcial"].replace("P", "")),
            "unidad": int(data["unidad"].replace("U", "")),
            "tema": f"Tema {data['tema'].replace('T', '')}",
            "unidad_nombre": f"Unidad {data['unidad'].replace('U', '')}"
        }
