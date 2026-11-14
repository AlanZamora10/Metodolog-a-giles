"""
Moodle simulado y utilidades compartidas por las pruebas del Sprint 3.

Curso 2 (SOF-POO-A) lo dicta rgomez@uta.edu.ec; curso 3 (SOF-ED-B) lo dicta otro docente.
Estudiantes del curso 2:
  U-03 Camila Andrade   -> aceptable, sin alerta
  U-04 Diego Curillo    -> R1 (nota < 5) con nota 0 y SIN ENTREGA
  U-11 Sebastián Romero -> R2 (U1 8.00 -> U2 5.00, nota 6.50): sólo alerta, nivel EN_RIESGO
  U-09 Andrés Salazar   -> aceptable, con U2-P3 PENDIENTE
"""

from app import repositories
from app.services.auth_service import create_access_token
from app.services.moodle_client import CredencialesMoodleInvalidas, MoodleError

DOCENTE = {"email": "rgomez@uta.edu.ec", "password": "Docente2026!"}
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


# ------------------------------------------------------------------ Login unificado (Fase A)
USUARIOS_MOODLE = {
    "rgomez": {"id": 10, "username": "rgomez", "email": "rgomez@uta.edu.ec", "fullname": "Ing. Roberto Gómez",
               "idnumber": "U-01", "password": "Docente2026!", "cursos": {2: "editingteacher", 4: "editingteacher"}},
    "otrodocente": {"id": 20, "username": "otrodocente", "email": "otro.docente@uta.edu.ec",
                    "fullname": "Ing. Otro Docente", "idnumber": "U-90", "password": "OtroDocente2026!",
                    "cursos": {3: "editingteacher"}},
    "dcurillo": {"id": 12, "username": "dcurillo", "email": "dcurillo@uta.edu.ec", "fullname": "Diego Curillo",
                 "idnumber": "U-04", "password": "Estudiante2026!", "cursos": {2: "student", 3: "student"}},
}
CURSOS_MOODLE = {2: "SOF-POO-A", 3: "SOF-ED-B", 4: "SOF-MA-B", 9: "OTRO-CURSO"}


class FakeMoodleAuth:
    """Moodle simulado para login/token.php, core_user_get_users_by_field y matrícula con roles."""

    caido = False

    async def obtener_token_usuario(self, username, password):
        if FakeMoodleAuth.caido:
            raise MoodleError("No se pudo contactar a Moodle en http://moodle:8080")
        u = USUARIOS_MOODLE.get(username)
        if not u or u["password"] != password:
            raise CredencialesMoodleInvalidas("Invalid login, please try again")
        return f"token-{username}"

    async def buscar_usuario(self, campo, valor):
        if FakeMoodleAuth.caido:
            raise MoodleError("No se pudo contactar a Moodle en http://moodle:8080")
        for u in USUARIOS_MOODLE.values():
            if str(u.get(campo)).lower() == str(valor).lower():
                return {k: v for k, v in u.items() if k not in ("password", "cursos")}
        return None

    async def get_users_courses(self, user_id):
        u = next(u for u in USUARIOS_MOODLE.values() if u["id"] == user_id)
        return [{"id": cid, "shortname": CURSOS_MOODLE[cid], "idnumber": CURSOS_MOODLE[cid]} for cid in u["cursos"]]

    async def get_enrolled_users(self, course_id):
        return [{"id": u["id"], "email": u["email"], "roles": [{"shortname": u["cursos"][course_id]}]}
                for u in USUARIOS_MOODLE.values() if course_id in u["cursos"]]


def token_con_rol(rol, email="usuario.prueba@uta.edu.ec"):
    """Perfil local con un rol distinto de DOCENTE (no obtenible por login) y su JWT, para probar 403."""
    usuario = repositories.upsert_usuario_moodle({"email": email, "nombres": f"Usuario {rol}", "rol": rol})
    token = create_access_token({"sub": usuario["email"], "rol": rol, "id": usuario["id"]})
    return {"Authorization": f"Bearer {token}"}
