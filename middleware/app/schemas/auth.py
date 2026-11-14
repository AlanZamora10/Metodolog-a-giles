from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    nombres: str = Field(..., min_length=3, max_length=120, json_schema_extra={"example": "Ing. Roberto Gómez"})
    email: str = Field(..., json_schema_extra={"example": "rgomez@uta.edu.ec"})
    password: str = Field(..., min_length=6)
    rol: str = Field(..., json_schema_extra={"example": "DOCENTE"}) # DOCENTE, ESTUDIANTE, ADMIN
    id_number: Optional[str] = Field(None, json_schema_extra={"example": "U-01"})


class UserLoginRequest(BaseModel):
    # Correo o nombre de usuario de Moodle UTA (Fase A: login unificado contra Moodle)
    email: str = Field(..., min_length=1, json_schema_extra={"example": "rgomez@uta.edu.ec"})
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: int
    nombres: str
    email: str
    rol: str
    id_number: Optional[str] = None
    activo: bool = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
