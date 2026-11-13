"""
==============================================================================
SERVICIO: AUTENTICACIÓN Y CONTROL DE ROLES (FISEI - UTA)
Responsables: Justin Ojeda (Backend) y Alvaro Moreta (Frontend & Roles)
==============================================================================
Este archivo maneja:
  1. Hashing seguro de contraseñas (PBKDF2-HMAC-SHA256, 100 000 iteraciones).
  2. Generación y validación de tokens JWT (secreto y duración desde variables de entorno).
  3. Registro y validación de usuarios en la tabla `usuarios` (Sprint 3: persistencia real).
  4. Cuentas semilla (docente, estudiante, administrador) con contraseñas tomadas del entorno.
==============================================================================
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from app import database, repositories
from app.config import settings

logger = logging.getLogger("edumonitor.auth")

ITERACIONES_PBKDF2 = 100000
ROLES_VALIDOS = ("DOCENTE", "ESTUDIANTE", "ADMIN")

# Cuentas semilla: los datos de identidad son públicos; las contraseñas llegan sólo por entorno.
CUENTAS_SEMILLA = (
    ("Ing. Roberto Gómez", "docente@uta.edu.ec", "DOCENTE", "U-01", "SEED_DOCENTE_PASSWORD"),
    ("Diego Curillo", "dcurillo@uta.edu.ec", "ESTUDIANTE", "U-04", "SEED_ESTUDIANTE_PASSWORD"),
    ("Administrador 1", "admin@uta.edu.ec", "ADMIN", "U-02", "SEED_ADMIN_PASSWORD"),
)


def _jwt_secret() -> str:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET no está configurado en el entorno.")
    return settings.JWT_SECRET


def hash_password(password: str) -> str:
    """
    Convierte una contraseña en texto plano en un hash seguro usando PBKDF2.
    Se utiliza un 'salt' aleatorio para evitar ataques por tablas arcoíris.
    """
    salt = secrets.token_hex(16)
    clave_hasheada = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        iterations=ITERACIONES_PBKDF2
    )
    # Guardamos en formato: salt$hash_hexadecimal
    return f"{salt}${clave_hasheada.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si la contraseña ingresada coincide con el hash almacenado.
    """
    try:
        salt, clave_guardada = hashed_password.split("$")
        clave_calculada = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=plain_password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            iterations=ITERACIONES_PBKDF2
        )
        return secrets.compare_digest(clave_calculada.hex(), clave_guardada)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea y firma un token JWT con tiempo de caducidad.
    """
    datos_a_codificar = data.copy()
    duracion = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    ahora = datetime.now(timezone.utc)
    datos_a_codificar.update({"exp": ahora + duracion, "iat": ahora})
    return jwt.encode(datos_a_codificar, _jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica un token JWT. Si es inválido o expiró, retorna None.
    """
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[settings.JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


@database.on_ready
def asegurar_cuentas_semilla(engine) -> None:
    """Crea o repara (hash inválido o desactualizado) las cuentas semilla definidas por entorno."""
    for nombres, email, rol, id_number, variable in CUENTAS_SEMILLA:
        password = getattr(settings, variable)
        if not password:
            logger.warning("Cuenta semilla %s omitida: %s no está definida.", email, variable)
            continue
        usuario = repositories.user_by_email(email, engine)
        if usuario is None:
            repositories.insert_user({
                "nombres": nombres, "email": email, "password_hash": hash_password(password),
                "rol": rol, "id_number": id_number, "activo": True,
            }, engine)
        elif not verify_password(password, usuario["password_hash"]):
            repositories.update_user(usuario["id"], {"password_hash": hash_password(password)}, engine)


class AuthService:
    """
    Servicio con las operaciones principales de gestión de usuarios (tabla `usuarios`).
    """

    @classmethod
    def get_user_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        """Busca un usuario por su correo institucional."""
        if not email:
            return None
        return repositories.user_by_email(email)

    @classmethod
    def register_user(
        cls,
        nombres: str,
        email: str,
        password: str,
        rol: str,
        id_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Registra un nuevo usuario en el sistema.
        Valida que el correo no esté duplicado y que el rol sea válido.
        """
        correo_limpio = email.strip().lower()
        if cls.get_user_by_email(correo_limpio):
            raise ValueError(f"El correo '{email}' ya se encuentra registrado.")

        rol_limpio = rol.strip().upper()
        if rol_limpio not in ROLES_VALIDOS:
            raise ValueError("El rol debe ser 'DOCENTE', 'ESTUDIANTE' o 'ADMIN'.")

        usuario = repositories.insert_user({
            "nombres": nombres.strip(),
            "email": correo_limpio,
            "password_hash": hash_password(password),
            "rol": rol_limpio,
            "id_number": id_number.strip().upper() if id_number else None,
            "activo": True,
        })
        if not usuario.get("id_number"):
            repositories.update_user(usuario["id"], {"id_number": f"U-{usuario['id']:02d}"})
            usuario["id_number"] = f"U-{usuario['id']:02d}"
        return usuario

    @classmethod
    def authenticate_user(cls, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verifica las credenciales en el inicio de sesión.
        Retorna el usuario si el correo y la contraseña son válidos y la cuenta está activa.
        """
        usuario = cls.get_user_by_email(email)
        if not usuario or usuario.get("activo") is False:
            return None
        if not verify_password(password, usuario["password_hash"]):
            return None
        return usuario
