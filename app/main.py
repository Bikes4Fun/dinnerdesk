"""Dinnerdesk API + static UI. Bind 127.0.0.1 only; share through ngrok."""

from __future__ import annotations

import os
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.domain.ingredient_photos import photo_directory, photo_file
from app.domain.recipe_photos import photo_allowed
from app.auth_routes import router as auth_router
from app.assets import food_dir
from app.db.database import connect, init_db
from app.routes import router
from app.taste_lab import router as taste_router

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"
FOOD = food_dir()
DEV_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


def _food_roots() -> list[Path]:
    return [food_dir()]


def _food_file(name: str) -> Path | None:
    if not name or name.startswith("."):
        return None
    name = name.split("/")[-1].split("\\")[-1]
    if not name or name.startswith("."):
        return None
    for root in _food_roots():
        if not root.is_dir():
            continue
        candidate = (root / name).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if not candidate.is_file() or not photo_allowed(name):
            continue
        head = candidate.read_bytes()[:24]
        if head.startswith(b"version https://git-lfs"):
            continue
        return candidate
    return None


def create_app() -> FastAPI:
    photo_directory()  # Reject invalid configured galleries before accepting requests.
    app = FastAPI(
        title="Dinnerdesk",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEV_ORIGINS),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=True,
    )
    app.include_router(router, prefix="/api")
    app.include_router(taste_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")

    @app.middleware("http")
    async def no_cache_api(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict):
            return JSONResponse(exc.detail, status_code=exc.status_code)
        return JSONResponse(
            {"error": "http", "detail": str(exc.detail)},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def hidden_error(_request: Request, _exc: Exception):
        logging.getLogger(__name__).error("Request failed", exc_info=_exc)
        return JSONResponse(
            {"error": "server_error", "detail": "unexpected"},
            status_code=500,
        )

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/food/{name}")
    def food_file(name: str):
        # Explicit route so the SPA catch-all cannot return index.html for photos.
        path = _food_file(name)
        if path is None:
            raise HTTPException(404, {"error": "not_found", "detail": "photo"})
        return FileResponse(path)

    @app.get("/grocery-food/{name}")
    def grocery_food_file(name: str):
        path = photo_file(name)
        if path is None:
            raise HTTPException(404, {"error": "not_found", "detail": "ingredient photo"})
        return FileResponse(path)

    taste_web = ROOT / "tastelab" / "web"
    if taste_web.is_dir():
        app.mount("/tastelab", StaticFiles(directory=taste_web, html=True), name="tastelab")

    if DIST.is_dir():
        assets = DIST / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            if path.startswith("api/") or path.startswith("food/"):
                raise HTTPException(404, {"error": "not_found", "detail": "route"})
            target = DIST / path
            if path and target.is_file():
                return FileResponse(target)
            return FileResponse(
                DIST / "index.html",
                headers={"Cache-Control": "no-store"},
            )

    @app.on_event("startup")
    def startup():
        conn = connect()
        init_db(conn)
        conn.close()
        # Catalog imports are deliberate CLI operations, never startup work.

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
