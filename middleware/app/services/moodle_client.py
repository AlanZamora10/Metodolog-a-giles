"""
Cliente HTTP para los Web Services REST de Moodle UTA.

Usa las variables de entorno:
  - MOODLE_URL          URL interna del contenedor (p. ej. http://moodle:8080)
  - MOODLE_HOST_HEADER  Host público con el que Moodle construye su wwwroot (p. ej. localhost)
  - MOODLE_TOKEN        Token del servicio externo EduMonitor_WS
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger("moodle_client")


class MoodleError(Exception):
    """Error al comunicarse con Moodle o excepción devuelta por el Web Service."""


class MoodleClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        host_header: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.MOODLE_URL).rstrip("/")
        self.token = token if token is not None else settings.MOODLE_TOKEN
        self.host_header = host_header if host_header is not None else settings.MOODLE_HOST_HEADER
        self.timeout = timeout or settings.MOODLE_TIMEOUT_SECONDS
        self.endpoint = f"{self.base_url}{settings.MOODLE_ENDPOINT}"

    def _headers(self) -> Dict[str, str]:
        return {"Host": self.host_header} if self.host_header else {}

    async def call(self, wsfunction: str, **params: Any) -> Any:
        """Invoca una función del Web Service REST y devuelve el JSON decodificado."""
        if not self.token:
            raise MoodleError("MOODLE_TOKEN no está configurado.")

        query = {
            "wstoken": self.token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
            **params,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint, data=query, headers=self._headers())
        except httpx.HTTPError as ex:
            raise MoodleError(f"No se pudo contactar a Moodle en {self.base_url}: {ex}") from ex

        if response.status_code != 200:
            raise MoodleError(
                f"Moodle respondió HTTP {response.status_code} en {wsfunction} "
                "(¿Web Services/REST habilitados y siembra ejecutada?)."
            )
        try:
            data = response.json()
        except ValueError as ex:
            raise MoodleError(f"Respuesta no JSON de Moodle en {wsfunction}.") from ex

        if isinstance(data, dict) and "exception" in data:
            raise MoodleError(f"{wsfunction}: {data.get('message', data.get('errorcode'))}")
        return data

    async def test_connection(self) -> Dict[str, Any]:
        try:
            info = await self.call("core_webservice_get_site_info")
            return {
                "conectado": True,
                "modo": "produccion",
                "sitio": info.get("sitename"),
                "version": info.get("release"),
                "moodle_url": self.base_url,
            }
        except MoodleError as ex:
            return {"conectado": False, "modo": "error", "mensaje": str(ex), "moodle_url": self.base_url}

    async def get_courses(self) -> List[Dict[str, Any]]:
        """Cursos de Moodle (excluye la portada del sitio, id=1)."""
        courses = await self.call("core_course_get_courses")
        return [c for c in courses if c.get("id") != 1]

    async def get_enrolled_users(self, course_id: int) -> List[Dict[str, Any]]:
        return await self.call("core_enrol_get_enrolled_users", courseid=course_id)

    async def get_grade_items(self, course_id: int) -> List[Dict[str, Any]]:
        """Libro de calificaciones (usergrades) de todos los usuarios del curso."""
        data = await self.call("gradereport_user_get_grade_items", courseid=course_id)
        return data.get("usergrades", [])

    # ------------------------------------------------------------------ Login unificado (Fase A)
    async def obtener_token_usuario(self, username: str, password: str) -> str:
        """
        Valida usuario y contraseña de Moodle con login/token.php (servicio MOODLE_LOGIN_SERVICE).
        Devuelve el token del usuario; lanza CredencialesMoodleInvalidas si Moodle las rechaza.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/login/token.php",
                    data={"username": username, "password": password, "service": settings.MOODLE_LOGIN_SERVICE},
                    headers=self._headers(),
                )
        except httpx.HTTPError as ex:
            raise MoodleError(f"No se pudo contactar a Moodle en {self.base_url}: {ex}") from ex
        if response.status_code != 200:
            raise MoodleError(f"Moodle respondió HTTP {response.status_code} en login/token.php.")
        try:
            data = response.json()
        except ValueError as ex:
            raise MoodleError("Respuesta no JSON de Moodle en login/token.php.") from ex
        if data.get("token"):
            return data["token"]
        if data.get("errorcode") in ("invalidlogin", "usernotconfirmed", "suspended", "restoredaccountresetpassword"):
            raise CredencialesMoodleInvalidas(data.get("error") or "Credenciales inválidas.")
        raise MoodleError(f"login/token.php: {data.get('error') or data.get('errorcode') or 'sin token'}")

    async def buscar_usuario(self, campo: str, valor: str) -> Optional[Dict[str, Any]]:
        """Usuario de Moodle por campo (email, username, id, idnumber)."""
        usuarios = await self.call("core_user_get_users_by_field", field=campo, **{"values[0]": valor})
        return usuarios[0] if usuarios else None

    async def get_users_courses(self, user_id: int) -> List[Dict[str, Any]]:
        """Cursos en los que está matriculado un usuario."""
        return await self.call("core_enrol_get_users_courses", userid=user_id)

    # ------------------------------------------------------------------ Publicación real (plugin local_edumonitor)
    async def crear_tarea_refuerzo(self, course_id: int, nombre: str, instrucciones: str, email_estudiante: str,
                                   fecha_entrega: int, codigo: str) -> Dict[str, Any]:
        """
        Crea (o devuelve, si ya existe con el mismo código) una tarea en la sección «Refuerzos» del curso,
        visible sólo para el estudiante indicado. Requiere el plugin local_edumonitor en Moodle.
        """
        return await self.call(
            "local_edumonitor_crear_tarea",
            courseid=course_id, nombre=nombre, instrucciones=instrucciones,
            emailestudiante=email_estudiante, fechaentrega=fecha_entrega, codigo=codigo,
        )


class CredencialesMoodleInvalidas(MoodleError):
    """Moodle rechazó el usuario o la contraseña."""
