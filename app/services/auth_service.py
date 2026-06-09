# app/services/auth_service.py

from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import os
import json
import uuid
from typing import Optional, Dict, Any

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)

oauth2_scheme = HTTPBearer()
ALGORITHM = "HS256"

USERS_FILE = os.path.join("data", "users.json")


class AuthService:

    @staticmethod
    def _ensure_users_file() -> None:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        if not os.path.exists(USERS_FILE):
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    @staticmethod
    def _load_users() -> list:
        AuthService._ensure_users_file()
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []

    @staticmethod
    def _save_users(users: list) -> None:
        AuthService._ensure_users_file()
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)

    @staticmethod
    def hash_password(password: str) -> str:
        if isinstance(password, bytes):
            password = password.decode("utf-8", errors="ignore")
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(
        plain_password: str,
        hashed_password: str,
    ) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(user_id: str) -> str:
        expire = datetime.utcnow() + timedelta(days=settings.access_token_expire_days)
        payload = {
            "sub": user_id,
            "exp": expire,
        }
        return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

    # New methods
    @staticmethod
    def register(email: str, password: str, tenant_id: str, full_name: Optional[str] = None) -> Dict[str, Any]:
        users = AuthService._load_users()
        if any(u.get("email") == email for u in users):
            raise ValueError("User with that email already exists")
        user_id = str(uuid.uuid4())
        hashed = AuthService.hash_password(password)
        user = {
            "id": user_id,
            "email": email,
            "tenant_id": tenant_id,
            "plan": "free",
            "full_name": full_name or "",
            "hashed_password": hashed,
            "created_at": datetime.utcnow().isoformat(),
        }
        users.append(user)
        AuthService._save_users(users)
        # return user without hashed password
        safe_user = {k: v for k, v in user.items() if k != "hashed_password"}
        return safe_user

    @staticmethod
    def login(email: str, password: str) -> str:
        users = AuthService._load_users()
        user = next((u for u in users if u.get("email") == email), None)
        if not user:
            raise ValueError("Invalid credentials")
        if not AuthService.verify_password(password, user.get("hashed_password", "")):
            raise ValueError("Invalid credentials")
        token = AuthService.create_access_token(user.get("id"))
        return token

    @staticmethod
    def get_user(user_id: str) -> Optional[Dict[str, Any]]:
        users = AuthService._load_users()
        user = next(
            (u for u in users if u.get("id") == user_id or u.get("email") == user_id),
            None,
        )
        if not user:
            return None
        safe_user = {k: v for k, v in user.items() if k != "hashed_password"}
        return safe_user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
):
    token = credentials.credentials
    payload = AuthService.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    user = AuthService.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user