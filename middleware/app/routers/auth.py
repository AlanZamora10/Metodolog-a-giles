from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app import repositories
from app.schemas.auth import (
    UserLoginRequest,
    UserResponse,
    TokenResponse
)
from app.services.auth_service import (
    AuthService,
    LoginRechazado,
    MoodleError,
    create_access_token,
    decode_access_token
)

router = APIRouter(prefix="/auth", tags=["Autenticación y Roles"])
security = HTTPBearer(auto_error=False)


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    """Dependencia para validar token JWT en endpoints protegidos (HU-14)."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación no proporcionado. Se requiere Bearer Token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado. Inicie sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = AuthService.get_user_by_email(payload.get("sub"))
    if not user or user.get("activo") is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_docente(user: dict = Depends(get_current_user)) -> dict:
    """Dependencia para endpoints exclusivos del rol DOCENTE (403 para otros roles)."""
    if user.get("rol") != "DOCENTE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso exclusivo para el rol DOCENTE.",
        )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest):
    """
    Login unificado con Moodle UTA (Fase A): correo o usuario de Moodle + contraseña de Moodle.
      - 401 si Moodle rechaza las credenciales.
      - 403 si el usuario no es docente de ningún curso del portafolio.
      - 503 si Moodle no está disponible para validar.
    """
    try:
        user = await AuthService.autenticar_docente(req.email, req.password)
    except LoginRechazado as ex:
        repositories.insert_log("LOGIN", "ADVERTENCIA", f"Acceso rechazado (no docente): {req.email.strip().lower()}",
                                {"usuario": req.email.strip().lower()})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(ex))
    except MoodleError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"No se pudo validar con Moodle UTA: {ex}")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repositories.insert_log("LOGIN", "EXITO", f"Inicio de sesión del docente {user['email']} (validado en Moodle).",
                            {"usuario": user["email"], "cursos": [c["shortname"] for c in user["cursos_docente"]]})
    token = create_access_token(data={"sub": user["email"], "rol": user["rol"], "id": user["id"]})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Obtiene los datos del usuario autenticado actual y su rol (HU-14).
    """
    return UserResponse(**current_user)
