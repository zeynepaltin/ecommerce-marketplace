"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

FastAPI application: middleware, routers and error pages.
Start from the repository root with:  uvicorn backend.app.main:app --reload
"""
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import DatabaseError
from .routers import admin, auth, customer, public, seller
from .session import ActivityMiddleware, AuthRequired, SessionManager
from .web import redirect, render

app = FastAPI(title="Moon Light Marketplace")
app.add_middleware(ActivityMiddleware)                       # inner: needs request.session
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret,
                   session_cookie="moonlight_session", same_site="lax")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

for module in (public, auth, customer, seller, admin):
    app.include_router(module.router)


@app.exception_handler(AuthRequired)
async def auth_required(request: Request, exc: AuthRequired):
    if exc.role is None:
        SessionManager.flash(request, "Please sign in to continue.", "warning")
        return redirect(f"/login?next={quote(request.url.path)}")
    return render(request, "error.html", code=403, message="You do not have permission to open this page.")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    message = exc.detail if exc.status_code == 404 else "The request could not be processed."
    response = render(request, "error.html", code=exc.status_code, message=message)
    response.status_code = exc.status_code
    return response


@app.exception_handler(DatabaseError)
async def db_error(request: Request, exc: DatabaseError):
    response = render(request, "error.html", code=500, message=exc.message)
    response.status_code = 500
    return response


@app.get("/health")
def health_check():
    return {"status": "ok"}
