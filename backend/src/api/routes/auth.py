"""Login endpoint — validates admin credentials and returns a Bearer token."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.src.infrastructure.config.settings import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str
    name: str


@router.post("/login")
def login(data: LoginRequest) -> LoginResponse:
    if data.email == settings.admin_email and data.password == settings.admin_password:
        return LoginResponse(
            token=settings.betterstack_api_token,
            email=data.email,
            name=data.email.split("@")[0],
        )
    raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
