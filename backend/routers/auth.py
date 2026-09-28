"""
OpsPulse 360 - Auth Router
Simple, real JWT-based authentication with two role types:
  - executive: read access to executive dashboards and all analytics
  - operations: read/write access to operations dashboard, inventory,
    delivery, and alert acknowledgement

Demo users (change in production / back with a real user table + hashed
passwords in Postgres):
    executive / exec123    (role=executive)
    ops       / ops123     (role=operations)

Endpoints:
    POST /api/auth/login   -> {access_token, role}
    GET  /api/auth/me      -> current user (requires Bearer token)
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

router = APIRouter()
security = HTTPBearer()

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "opspulse360-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Demo user store. In production: a real users table with bcrypt/argon2 hashes.
_USERS = {
    "executive": {"password": "exec123", "role": "executive", "name": "Executive User"},
    "ops": {"password": "ops123", "role": "operations", "name": "Operations User"},
}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"username": payload["sub"], "role": payload["role"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*allowed_roles: str):
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Requires role in {allowed_roles}")
        return user
    return dependency


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    user = _USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(req.username, user["role"])
    return TokenResponse(access_token=token, role=user["role"], name=user["name"])


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
