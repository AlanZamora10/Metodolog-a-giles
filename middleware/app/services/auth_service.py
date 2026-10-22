import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import jwt

from app.config import settings

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_uta_fisei_2026_sprint1")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))


def hash_password(password: str) -> str:
    """Genera hash seguro de contraseña usando PBKDF2-HMAC-SHA256 con salt aleatorio."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con el hash almacenado."""
    try:
        salt, key_hex = hashed_password.split("$")
        computed_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return secrets.compare_digest(computed_key.hex(), key_hex)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Genera un token JWT firmado."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica y valida la firma y vigencia de un token JWT."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# Almacén de usuarios precargados para pruebas y demostración de roles
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
    @classmethod
    def get_user_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        for user in USERS_DB:
            if user["email"].strip().lower() == email.strip().lower():
                return user
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
        email_clean = email.strip().lower()
        if cls.get_user_by_email(email_clean):
            raise ValueError(f"El correo '{email}' ya se encuentra registrado.")

        rol_normalizado = rol.strip().upper()
        if rol_normalizado not in ["DOCENTE", "ESTUDIANTE", "ADMIN"]:
            raise ValueError("El rol debe ser 'DOCENTE', 'ESTUDIANTE' o 'ADMIN'.")

        new_user = {
            "id": len(USERS_DB) + 1,
            "nombres": nombres.strip(),
            "email": email_clean,
            "password_hash": hash_password(password),
            "rol": rol_normalizado,
            "id_number": id_number.strip().upper() if id_number else f"U-{len(USERS_DB)+1:02d}",
            "activo": True
        }
        USERS_DB.append(new_user)
        return new_user

    @classmethod
    def authenticate_user(cls, email: str, password: str) -> Optional[Dict[str, Any]]:
        user = cls.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user
