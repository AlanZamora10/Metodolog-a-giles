"""
==============================================================================
SERVICIO: AUTENTICACIÓN Y CONTROL DE ROLES (FISEI - UTA)
Responsables: Justin Ojeda (Backend) y Alvaro Moreta (Frontend & Roles)
==============================================================================
Fase A — Login unificado con Moodle:
  1. El docente inicia sesión con su correo (o usuario) y contraseña de Moodle UTA.
  2. Las credenciales se validan contra Moodle (login/token.php); EduMonitor no guarda contraseñas.
  3. Sólo se admite a quien es profesor (editingteacher / teacher) en al menos un curso del portafolio
     (prefijo MOODLE_COURSE_PREFIX, p. ej. SOF-).
  4. Se guarda/actualiza el perfil en la tabla `usuarios` y se emite el JWT de EduMonitor
     (secreto y duración desde variables de entorno).
Se conservan hash_password/verify_password (PBKDF2-HMAC-SHA256, 100 000 iteraciones) para cuentas
locales de servicio si se necesitaran; los docentes ya no tienen contraseña local.
==============================================================================
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt

from app import repositories
from app.config import settings
from app.services.moodle_client import CredencialesMoodleInvalidas, MoodleClient, MoodleError

logger = logging.getLogger("edumonitor.auth")

ITERACIONES_PBKDF2 = 100000
ROLES_DOCENTE_MOODLE = {"editingteacher", "teacher"}


class LoginRechazado(Exception):
    """Credenciales válidas en Moodle, pero el usuario no es docente de ningún curso del portafolio."""


def _jwt_secret() -> str:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET no está configurado en el entorno.")
    return settings.JWT_SECRET


def hash_password(password: str) -> str:
    """Hash PBKDF2-HMAC-SHA256 (salt aleatorio de 16 bytes, 100 000 iteraciones): salt$hash_hex."""
    salt = secrets.token_hex(16)
    clave = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERACIONES_PBKDF2)
    return f"{salt}${clave.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, clave_guardada = hashed_password.split("$")
        clave = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"),
                                    ITERACIONES_PBKDF2)
        return secrets.compare_digest(clave.hex(), clave_guardada)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Crea y firma un token JWT con tiempo de caducidad."""
    datos = data.copy()
    ahora = datetime.now(timezone.utc)
    datos.update({"exp": ahora + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)),
                  "iat": ahora})
    return jwt.encode(datos, _jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica un token JWT. Si es inválido o expiró, retorna None."""
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[settings.JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _roles(user: Dict[str, Any]) -> set:
    return {r.get("shortname") for r in user.get("roles", [])}


async def _cursos_como_docente(client: MoodleClient, user_id: int) -> List[Dict[str, Any]]:
    """Cursos del portafolio (prefijo) donde el usuario tiene rol de profesor en Moodle."""
    prefijo = settings.MOODLE_COURSE_PREFIX.upper()
    cursos = [
        c for c in await client.get_users_courses(user_id)
        if not prefijo or (c.get("idnumber") or c.get("shortname") or "").upper().startswith(prefijo)
    ]
    propios = []
    for curso in cursos:
        for participante in await client.get_enrolled_users(curso["id"]):
            if participante.get("id") == user_id and _roles(participante) & ROLES_DOCENTE_MOODLE:
                propios.append({"id": curso["id"], "shortname": curso.get("shortname")})
                break
    return propios


class AuthService:
    """Autenticación de docentes contra Moodle y consulta de perfiles locales."""

    @classmethod
    def get_user_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        if not email:
            return None
        return repositories.user_by_email(email)

    @classmethod
    async def autenticar_docente(cls, identificador: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Valida las credenciales contra Moodle. Devuelve el perfil local del docente, None si las
        credenciales son inválidas, lanza LoginRechazado si no es docente y MoodleError si Moodle no responde.
        """
        identificador = (identificador or "").strip()
        if not identificador or not password:
            return None
        client = MoodleClient()

        usuario = None
        if "@" in identificador:
            usuario = await client.buscar_usuario("email", identificador.lower())
            if usuario is None:
                return None
            username = usuario["username"]
        else:
            username = identificador.lower()

        try:
            await client.obtener_token_usuario(username, password)
        except CredencialesMoodleInvalidas:
            return None

        usuario = usuario or await client.buscar_usuario("username", username)
        if usuario is None or not usuario.get("email"):
            return None

        cursos = await _cursos_como_docente(client, usuario["id"])
        if not cursos:
            raise LoginRechazado("EduMonitor AI es de uso exclusivo para docentes de los cursos del portafolio.")

        perfil = repositories.upsert_usuario_moodle({
            "email": usuario["email"],
            "nombres": usuario.get("fullname") or f"{usuario.get('firstname', '')} {usuario.get('lastname', '')}",
            "rol": "DOCENTE",
            "id_number": usuario.get("idnumber") or None,
            "moodle_user_id": usuario["id"],
            "moodle_username": usuario.get("username"),
        })
        perfil["cursos_docente"] = cursos
        return perfil


__all__ = [
    "AuthService", "LoginRechazado", "MoodleError", "create_access_token", "decode_access_token",
    "hash_password", "verify_password",
]
