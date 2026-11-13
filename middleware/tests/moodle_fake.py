"""
Moodle simulado y utilidades compartidas por las pruebas del Sprint 3.

Curso 2 (SOF-POO-A) lo dicta docente@uta.edu.ec; curso 3 (SOF-ED-B) lo dicta otro docente.
Estudiantes del curso 2:
  U-03 Camila Andrade   -> aceptable, sin alerta
  U-04 Diego Curillo    -> R1 (nota < 5) con nota 0 y SIN ENTREGA
  U-11 Sebastián Romero -> R2 (U1 8.00 -> U2 5.00, nota 6.50): sólo alerta, nivel EN_RIESGO
  U-09 Andrés Salazar   -> aceptable, con U2-P3 PENDIENTE
"""

from app.services.moodle_client import MoodleError

DOCENTE = {"email": "docente@uta.edu.ec", "password": "Docente2026!"}
ESTUDIANTE = {"email": "dcurillo@uta.edu.ec", "password": "Estudiante2026!"}
OTRO_DOCENTE = {"email": "otro.docente@uta.edu.ec", "password": "OtroDocente2026!"}


def gi(idnumber, raw=None, feedback="", grademax=10):
    return {"idnumber": idnumber, "itemname": f"Actividad {idnumber}", "graderaw": raw,
            "grademax": grademax, "feedback": feedback}


def _alumno(uid, nombre, idn, email):
    return {"id": uid, "fullname": nombre, "email": email, "idnumber": idn, "roles": [{"shortname": "student"}]}


class FakeMoodleSprint3:
    def __init__(self, recuperado: bool = False, fail: bool = False):
        self.recuperado = recuperado  # True: U-11 recupera en la Unidad 2 (deja de cumplir R2)
        self.fail = fail

    async def call(self, wsfunction, **params):
        if self.fail:
            raise MoodleError("Moodle respondió HTTP 503")
        return {"sitename": "Moodle UTA", "release": "4.3.2"}

    async def get_courses(self):
        return [
            {"id": 2, "shortname": "SOF-POO-A", "idnumber": "SOF-POO-A",
             "fullname": "(SOF) PROGRAMACION ORIENTADA A OBJETOS - A"},
            {"id": 3, "shortname": "SOF-ED-B", "idnumber": "SOF-ED-B", "fullname": "(SOF) ESTRUCTURA DE DATOS - B"},
        ]

    async def get_enrolled_users(self, course_id):
        profesor = DOCENTE["email"] if course_id == 2 else OTRO_DOCENTE["email"]
        return [
            {"id": 10, "fullname": "Profesor", "email": profesor, "roles": [{"shortname": "editingteacher"}]},
            _alumno(11, "Camila Andrade", "U-03", "candrade@uta.edu.ec"),
            _alumno(12, "Diego Curillo", "U-04", "dcurillo@uta.edu.ec"),
            _alumno(13, "Sebastián Romero", "U-11", "sromero@uta.edu.ec"),
            _alumno(14, "Andrés Salazar", "U-09", "asalazar@uta.edu.ec"),
        ]

    async def get_grade_items(self, course_id):
        u2 = 8.0 if self.recuperado else 5.0
        return [
            {"userid": 11, "gradeitems": [gi("U1-A1", 8.5), gi("U1-T1", 8.5), gi("U1-P1", 8.5),
                                          gi("U2-A2", 8.5), gi("U2-T3", 8.5), gi("U2-P3", 8.5)]},
            {"userid": 12, "gradeitems": [gi("U1-A1", 3.0), gi("U1-T1", 4.0), gi("U1-T2", 0.0),
                                          gi("U2-T4", 0.0, "SIN ENTREGA"), gi("U1-P1", 3.5)]},
            {"userid": 13, "gradeitems": [gi("U1-A1", 8.0), gi("U1-T1", 8.0), gi("U1-P1", 8.0),
                                          gi("U2-A2", u2), gi("U2-T3", u2), gi("U2-P3", u2)]},
            {"userid": 14, "gradeitems": [gi("U1-A1", 7.5), gi("U1-T1", 8.0), gi("U1-P1", 7.5),
                                          gi("U2-P3", None, "PENDIENTE DE REVISIÓN")]},
        ]
