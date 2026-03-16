"""
SHA Fraud Detection — Auth Routes

POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
PATCH /api/v1/auth/password
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser, get_db
from app.schemas.auth_schema import (
    AuthUserResponse,
    LogoutResponse,
    PasswordChangeRequest,
)
from app.schemas.base_schema import MessageResponse
from app.services.auth_service import AuthService

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


# def _set_auth_cookies(
#     response: Response, access_token: str, refresh_token: str, user_role: str
# ):
#     is_prod = settings.ENVIRONMENT == "production"

#     base_cookie = dict(
#         secure=is_prod,
#         samesite="strict" if is_prod else "lax",
#         httponly=True,
#     )

#     response.set_cookie(
#         key="auth_token",
#         value=access_token,
#         **base_cookie,
#         max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
#         path="/",
#     )
#     response.set_cookie(
#         key="refresh_token",
#         value=refresh_token,
#         **base_cookie,
#         max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
#         path="/api/v1/auth/refresh" if is_prod else "/",
#     )
#     response.set_cookie(
#         key="user_role",
#         value=user_role,
#         secure=is_prod,
#         samesite="strict" if is_prod else "lax",
#         httponly=False,  # middleware + JS needs to read this
#         max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
#         path="/",
#     )


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str, user_role: str
):
    is_prod = settings.ENVIRONMENT == "production"

    base_cookie = dict(
        secure=True,  # always True — required for samesite=none
        samesite="none",  # required for cross-origin (Vercel → your API)
        httponly=True,
        path="/",  # consistent path for all cookies
    )
    response.set_cookie(
        key="auth_token",
        value=access_token,
        **base_cookie,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        **base_cookie,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    response.set_cookie(
        key="user_role",
        value=user_role,
        secure=True,
        samesite="none",
        httponly=False,  # JS needs to read this
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@auth_router.post("/login", response_model=AuthUserResponse, summary="Login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request and request.client else None
    result = await AuthService.login(db, form_data.username, form_data.password, ip)
    # ✅ Join array to comma-separated string for cookie, parse back on frontend
    roles_str = ",".join(result.user.roles) if result.user.roles else "viewer"
    _set_auth_cookies(
        response,
        result.tokens.access_token,
        result.tokens.refresh_token,
        roles_str,  # e.g. "admin,investigator"
    )
    return result.user  # ✅ returns AuthUserResponse directly


@auth_router.post("/refresh", response_model=None, summary="Refresh access token")
async def refresh_token(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh = request.cookies.get("refresh_token")  # ← read from cookie
    if not raw_refresh:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    result = await AuthService.refresh(db, raw_refresh)
    response.set_cookie(
        key="auth_token",
        value=result.access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return {"ok": True}


@auth_router.post("/logout", response_model=LogoutResponse, summary="Logout")
async def logout(
    response: Response,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        await AuthService.logout(db, raw_refresh, current_user.id)
    # ✅ Clear both cookies
    response.delete_cookie("auth_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")
    return LogoutResponse()


@auth_router.patch(
    "/password", response_model=MessageResponse, summary="Change own password"
)
async def change_password(
    body: PasswordChangeRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Logged-in user changes their own password."""
    await AuthService.change_password(
        db, current_user, body.current_password, body.new_password
    )
    return MessageResponse(message="Password changed successfully")
