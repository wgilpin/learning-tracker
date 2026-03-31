"""Authentication routes: /login, /logout, /register."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

import os
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


def _htmx_redirect(response: Response, url: str) -> Response:
    """Set HX-Redirect for HTMX clients; fallback header for plain requests."""
    response.headers["HX-Redirect"] = url
    return response


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/login.html")


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.user import authenticate_user

    try:
        user = await authenticate_user(session, email=email, password=password)
    except ValueError as exc:
        hint = str(exc)
        if hint == "deactivated":
            return Response(status_code=403, content="Account deactivated")
        return Response(status_code=401, content="Invalid credentials")

    request.session["user_id"] = str(user.id)
    logger.info("Login successful user_id=%s", user.id)
    return _htmx_redirect(Response(status_code=200), "/")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@router.post("/logout")
async def logout(request: Request) -> Response:
    request.session.clear()
    return _htmx_redirect(Response(status_code=200), "/login")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/register.html")


@router.post("/register")
async def register(
    request: Request,
    invite_code: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if password != password_confirm:
        return Response(status_code=422, content="Passwords do not match")

    from documentlm_core.services.user import create_user_from_invite

    try:
        user = await create_user_from_invite(
            session,
            invite_code=invite_code,
            email=email,
            password=password,
        )
    except ValueError as exc:
        msg = str(exc)
        if "already registered" in msg:
            return Response(status_code=409, content=msg)
        return Response(status_code=400, content=msg)

    request.session["user_id"] = str(user.id)
    logger.info("Registration successful user_id=%s", user.id)
    return _htmx_redirect(Response(status_code=200), "/")
