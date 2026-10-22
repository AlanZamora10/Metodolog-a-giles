"""
==============================================================================
SERVICIO: AUTENTICACIÓN Y CONTROL DE ROLES (FISEI - UTA)
Responsables: Justin Ojeda (Backend) y Alvaro Moreta (Frontend & Roles)
==============================================================================
Este archivo maneja:
  1. Hashing seguro de contraseñas (PBKDF2-HMAC-SHA256).
  2. Generación y validación de tokens JWT.
  3. Registro y validación de usuarios (DOCENTE y ESTUDIANTE).
==============================================================================
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import jwt

# Parámetros de configuración del token JWT
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_uta_fisei_2026_sprint1")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DURACION_TOKEN_MINUTOS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))


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
        iterations=100000
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
            iterations=100000
        )
        return secrets.compare_digest(clave_calculada.hex(), clave_guardada)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea y firma un token JWT con tiempo de caducidad.
    """
    datos_a_codificar = data.copy()
    tiempo_expiracion = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=DURACION_TOKEN_MINUTOS))
    
    datos_a_codificar.update({
        "exp": tiempo_expiracion,
        "iat": datetime.now(timezone.utc)
    })
    
    token = jwt.encode(datos_a_codificar, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica un token JWT. Si es inválido o expiró, retorna None.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# Base de datos en memoria para pruebas rápidas y demostración del Sprint 1
USERS_DB: List[Dict[str, Any]] = [
    {
        "id": 1,
        "nombres": "Ing. Hernán Naranjo, Mg.",
        "email": "docente@uta.edu.ec",
        "password_hash": hash_password("Docente2026!"),
        "rol": "DOCENTE",
        "id_number": "U-01",
        "activo": True
    },
    {
        "id": 2,
        "nombres": "Estudiante C",
        "email": "estudiante.c@uta.edu.ec",
        "password_hash": hash_password("Estudiante2026!"),
        "rol": "ESTUDIANTE",
        "id_number": "U-05",
        "activo": True
    },
    {
        "id": 3,
        "nombres": "Administrador 1",
        "email": "admin@uta.edu.ec",
        "password_hash": hash_password("Admin2026!"),
        "rol": "ADMIN",
        "id_number": "U-02",
        "activo": True
    }
]


class AuthService:
    """
    Servicio con las operaciones principales de gestión de usuarios.
    """

    @classmethod
    def get_user_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        """Busca un usuario por su correo institucional."""
        correo_buscado = email.strip().lower()
        for usuario in USERS_DB:
            if usuario["email"].strip().lower() == correo_buscado:
                return usuario
        return None

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

        # Validar si ya existe el correo
        if cls.get_user_by_email(correo_limpio):
            raise ValueError(f"El correo '{email}' ya se encuentra registrado.")

        # Validar el rol
        rol_limpio = rol.strip().upper()
        if rol_limpio not in ["DOCENTE", "ESTUDIANTE", "ADMIN"]:
            raise ValueError("El rol debe ser 'DOCENTE', 'ESTUDIANTE' o 'ADMIN'.")

        # Crear y guardar nuevo usuario
        nuevo_id = len(USERS_DB) + 1
        nuevo_usuario = {
            "id": nuevo_id,
            "nombres": nombres.strip(),
            "email": correo_limpio,
            "password_hash": hash_password(password),
            "rol": rol_limpio,
            "id_number": id_number.strip().upper() if id_number else f"U-{nuevo_id:02d}",
            "activo": True
        }
        USERS_DB.append(nuevo_usuario)
        return nuevo_usuario

    @classmethod
    def authenticate_user(cls, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verifica las credenciales en el inicio de sesión.
        Retorna el usuario si el correo y la contraseña son válidos.
        """
        usuario = cls.get_user_by_email(email)
        if not usuario:
            return None
        
        # Validar la contraseña contra el hash
        if not verify_password(password, usuario["password_hash"]):
            return None
            
        return usuario
