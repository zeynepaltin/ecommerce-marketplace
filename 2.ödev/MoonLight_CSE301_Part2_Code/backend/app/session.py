"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Session handling: login state, flash messages, page history, idle timeout
and an in-memory tracker of the current activity of every signed-in user.
"""
import secrets
import threading
from datetime import datetime, timedelta

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from .config import settings

PAGE_TITLES = [
    ("/admin/users", "User management"), ("/admin/categories", "Categories"), ("/admin/orders", "All orders"),
    ("/admin/products", "Product moderation"), ("/admin", "Admin dashboard"),
    ("/seller/products", "My products"), ("/seller/orders", "Orders to ship"), ("/seller/shipments", "Shipments"),
    ("/seller", "Seller dashboard"), ("/products/", "Product detail"), ("/products", "Product catalogue"),
    ("/cart", "Shopping cart"), ("/checkout", "Checkout"), ("/orders/", "Order detail"), ("/orders", "My orders"),
    ("/addresses", "Addresses"), ("/reviews", "Reviews"), ("/account", "My session"), ("/login", "Login"),
    ("/register", "Registration"), ("/", "Home"),
]


def page_title(path: str) -> str:
    for prefix, title in PAGE_TITLES:
        if path == prefix or (prefix != "/" and path.startswith(prefix)):
            return title
    return path


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ActivityTracker:
    """Keeps, per session, who is signed in and what they are currently doing."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}

    def touch(self, sid: str, user: dict, path: str, ip: str, login_at: str):
        with self._lock:
            self._sessions[sid] = {"name": user["name"], "role": user["role"], "email": user["email"],
                                   "ip": ip, "login_at": login_at, "last_seen": now_iso(),
                                   "page": page_title(path), "path": path}

    def remove(self, sid: str | None):
        with self._lock:
            self._sessions.pop(sid, None)

    def online(self) -> list[dict]:
        limit = datetime.now() - timedelta(minutes=settings.session_idle_minutes)
        with self._lock:
            for sid in [s for s, v in self._sessions.items() if datetime.fromisoformat(v["last_seen"]) < limit]:
                del self._sessions[sid]
            return sorted(self._sessions.values(), key=lambda v: v["last_seen"], reverse=True)


tracker = ActivityTracker()


class SessionManager:
    """Helpers around request.session (a signed cookie managed by SessionMiddleware)."""

    @staticmethod
    def user(request: Request) -> dict | None:
        return request.session.get("user")

    @staticmethod
    def login(request: Request, account: dict, cart_count: int = 0):
        request.session.clear()
        request.session["sid"] = secrets.token_hex(16)
        request.session["user"] = {
            "id": account["UserID"], "email": account["Email"], "role": account["Role"],
            "name": account["DisplayName"], "customer_id": account["CustomerID"],
            "seller_id": account["SellerID"], "seller_status": account["SellerStatus"],
        }
        request.session["login_at"] = now_iso()
        request.session["last_activity"] = now_iso()
        request.session["cart_count"] = cart_count
        request.session["history"] = []
        request.session["recent_products"] = []

    @staticmethod
    def logout(request: Request):
        tracker.remove(request.session.get("sid"))
        request.session.clear()

    @staticmethod
    def flash(request: Request, message: str, category: str = "success"):
        request.session.setdefault("flashes", [])
        request.session["flashes"] = request.session["flashes"] + [[category, message]]

    @staticmethod
    def pop_flashes(request: Request) -> list:
        return request.session.pop("flashes", [])

    @staticmethod
    def remember_product(request: Request, product_id: int):
        recent = [p for p in request.session.get("recent_products", []) if p != product_id]
        request.session["recent_products"] = ([product_id] + recent)[:4]


class ActivityMiddleware(BaseHTTPMiddleware):
    """Runs inside SessionMiddleware: enforces the idle timeout and records activity."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/static") or path == "/favicon.ico":
            return await call_next(request)
        user = request.session.get("user")
        if user:
            last = datetime.fromisoformat(request.session.get("last_activity", now_iso()))
            if datetime.now() - last > timedelta(minutes=settings.session_idle_minutes):
                SessionManager.logout(request)
                SessionManager.flash(request, "Your session expired after a period of inactivity. Please sign in again.", "warning")
                return RedirectResponse("/login", status_code=303)
            request.session["last_activity"] = now_iso()
            if request.method == "GET":
                history = request.session.get("history", [])
                entry = {"path": str(request.url.path) + (f"?{request.url.query}" if request.url.query else ""),
                         "title": page_title(path), "at": now_iso()}
                request.session["history"] = ([entry] + [h for h in history if h["path"] != entry["path"]])[:8]
            tracker.touch(request.session["sid"], user, path, request.client.host if request.client else "-",
                          request.session.get("login_at", now_iso()))
        return await call_next(request)


class AuthRequired(Exception):
    def __init__(self, role: str | None = None):
        self.role = role


def require_role(*roles: str):
    """FastAPI dependency factory restricting a route to the given roles."""

    def dependency(request: Request) -> dict:
        user = request.session.get("user")
        if not user:
            raise AuthRequired()
        if roles and user["role"] not in roles:
            raise AuthRequired(user["role"])
        return user

    return dependency
