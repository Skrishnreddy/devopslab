"""One error shape for every failure: {"error": {"code", "message", "detail"}}."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("devopslab")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, detail: object | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.detail = status, code, message, detail


def _body(code: str, message: str, detail: object | None = None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail}}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, e: AppError):
        return JSONResponse(_body(e.code, e.message, e.detail), status_code=e.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}
        return JSONResponse(_body(code.get(e.status_code, "http_error"), str(e.detail)), status_code=e.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        return JSONResponse(_body("invalid_request", "Request validation failed", e.errors()), status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, e: Exception):
        log.exception("Unhandled error")
        return JSONResponse(_body("internal_error", f"{e.__class__.__name__}: {e}"), status_code=500)
