"""
==============================================================================
SERVICIO: PARSER DE ID NUMBER DE MOODLE (FISEI - UTA)
Responsable: Justin Ojeda (Backend) & Alan Zamora (Calidad)
==============================================================================
Este archivo analiza el campo 'ID number' de las actividades de Moodle
para asociarlas automáticamente con su Materia, Parcial, Unidad y Tema.

Convención normalizada requerida:
  [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]
  Ejemplo: MAT1-P1-U2-T3
==============================================================================
"""

import re
from typing import Dict, Any, Optional


class IDNumberParser:
    """
    Clase para validar y descomponer los códigos de actividad de Moodle.
    """

    # Expresión regular para verificar el patrón [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]
    # Ejemplo: MAT1-P1-U2-T3
    PATRON_ID = re.compile(
        r"^(?P<materia>[A-Za-z0-9]+)-(?P<parcial>P[12])-(?P<unidad>U[1-4])-(?P<tema>T\d+)$"
    )

    @classmethod
    def parse(cls, id_number: Optional[str]) -> Dict[str, Any]:
        """
        Analiza el ID de una tarea o actividad.
        
        Si el ID es válido, extrae:
          - materia (ej: 'MAT1')
          - parcial (ej: 1 o 2)
          - unidad (ej: 1, 2, 3 o 4)
          - tema (ej: 'Tema 3')
          
        Si no cumple el formato, lo marca como 'sin_clasificar' para auditoría (HU-04, HU-16).
        """
        # Paso 1: Validar que no sea nulo ni vacío
        if not id_number or not isinstance(id_number, str):
            return {
                "valido": False,
                "estado": "sin_clasificar",
                "id_original": id_number,
                "mensaje": "El ID number está vacío o no es una cadena de texto."
            }

        # Paso 2: Limpiar espacios y pasar a mayúsculas
        id_limpio = id_number.strip().upper()

        # Paso 3: Comprobar si coincide con el formato
        coincidencia = cls.PATRON_ID.match(id_limpio)
        if not coincidencia:
            return {
                "valido": False,
                "estado": "sin_clasificar",
                "id_original": id_number,
                "mensaje": f"El código '{id_number}' no sigue el formato [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]."
            }

        # Paso 4: Extraer las partes del diccionario
        datos = coincidencia.groupdict()
        numero_parcial = int(datos["parcial"].replace("P", ""))
        numero_unidad = int(datos["unidad"].replace("U", ""))
        numero_tema = datos["tema"].replace("T", "")

        return {
            "valido": True,
            "estado": "clasificado",
            "id_original": id_number,
            "materia": datos["materia"],
            "parcial": numero_parcial,
            "unidad": numero_unidad,
            "tema": f"Tema {numero_tema}",
            "unidad_nombre": f"Unidad {numero_unidad}"
        }
