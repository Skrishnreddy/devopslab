from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session as DB

from ...auth.deps import COOKIE, Principal, check_origin, current_principal
from ...auth.provider import auth_provider, create_session
from ...core.config import settings
from ...core.errors import AppError
from ...db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    token: str


@router.post("/login", status_code=204)
def login(body: LoginBody, request: Request, response: Response, db: DB = Depends(get_db)):
    check_origin(request)
    user = auth_provider.authenticate(db, body.token.strip())
    if user is None:
        raise AppError(401, "invalid_token", "That login token is not valid. Run `make token` to see it.")
    raw, _ = create_session(db, user, request.headers.get("user-agent"))
    response.set_cookie(COOKIE, raw, httponly=True, samesite="strict", secure=settings.cookie_secure,
                        max_age=settings.session_hours * 3600, path="/")


@router.post("/logout", status_code=204)
def logout(response: Response, p: Principal = Depends(current_principal), db: DB = Depends(get_db)):
    db.delete(db.merge(p.session))
    db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.get("/me")
def me(p: Principal = Depends(current_principal)):
    return {"id": p.user.id, "username": p.user.username, "role": p.user.role,
            "session_expires_at": p.session.expires_at}
