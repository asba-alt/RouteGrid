from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.auth import (
    SESSION_COOKIE,
    CurrentUser,
    get_current_user,
    verify_password,
    verify_username,
)
from app.core.config import settings
from app.core.security import check_login_rate_limit, reset_login_rate_limit
from app.core.session import create_session, delete_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=settings.SESSION_TTL_MINUTES * 60,
        httponly=True,  # not readable by JavaScript
        secure=settings.is_production,  # HTTPS only in production
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


@router.post("/login", response_model=CurrentUser)
async def login(
    payload: LoginRequest, request: Request, response: Response
) -> CurrentUser:
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is not configured on this server",
        )

    check_login_rate_limit(request)

    # Evaluate both checks so a wrong username and a wrong password cost the same.
    username_ok = verify_username(payload.username)
    password_ok = verify_password(payload.password)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    reset_login_rate_limit(request)

    user = CurrentUser(name=settings.OPERATOR_USERNAME, role="dispatcher")
    session_id = await create_session(
        {"id": str(user.id), "name": user.name, "role": user.role},
        settings.SESSION_TTL_MINUTES,
    )
    _set_session_cookie(response, session_id)
    return user


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        await delete_session(session_id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user
