from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(ORMModel):
    id: str
    email: EmailStr
    created_at: datetime
    last_login_at: datetime | None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
