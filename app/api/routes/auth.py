import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from app.services.auth_service import AuthService
from app.services.tenant_service import TenantService

router = APIRouter()
logger = logging.getLogger(__name__)
auth_service = AuthService()
tenant_service = TenantService()
security = HTTPBearer()


class RegisterRequest(BaseModel):
    email: str
    password: str
    tenant_id: str
    business_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/register")
async def register(request: RegisterRequest):
    """
    Register a new business owner.
    Also creates the tenant if it doesn't exist yet.
    """
    # Create tenant if needed
    existing = tenant_service.get_tenant(request.tenant_id)
    if not existing:
        tenant_service.create_tenant(request.tenant_id, request.business_name)

    try:
        user = auth_service.register(
            email=request.email,
            password=request.password,
            tenant_id=request.tenant_id,
        )
        return {
            "message": "Account created successfully",
            "user": user,
            "portal_url": f"/api/v1/portal/{request.tenant_id}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/login")
async def login(request: LoginRequest):
    """Login and receive a JWT token."""
    token = auth_service.login(request.email, request.password)

    if not token:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user = auth_service.get_user(request.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant_id": user["tenant_id"],
        "plan": user["plan"],
        "portal_url": f"/api/v1/portal/{user['tenant_id']}",
    }


@router.get("/auth/me")
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Returns the current logged-in user's info."""
    payload = auth_service.verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user = auth_service.get_user(payload["sub"])
    return user


# Reusable dependency — use this in any route that needs auth
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    auth = AuthService()
    payload = auth.verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return payload