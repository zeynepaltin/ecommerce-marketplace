"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Template rendering helpers.
"""
import math
from decimal import Decimal
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from .session import SessionManager

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def money(value) -> str:
    if value is None:
        return "-"
    return f"{Decimal(value):,.2f} ₺"


STATUS_COLORS = {
    "ACTIVE": "success", "COMPLETED": "success", "DELIVERED": "success",
    "PENDING": "warning", "PROCESSING": "info", "PREPARING": "warning", "SHIPPED": "primary",
    "OUT_OF_STOCK": "secondary", "INACTIVE": "secondary", "REFUNDED": "secondary",
    "SUSPENDED": "danger", "CANCELLED": "danger", "FAILED": "danger",
}
templates.env.filters["money"] = money
templates.env.globals["status_color"] = lambda s: STATUS_COLORS.get(s or "", "secondary")


def render(request: Request, name: str, **context):
    context.update(request=request, user=SessionManager.user(request), session=request.session,
                   flashes=SessionManager.pop_flashes(request))
    return templates.TemplateResponse(request, name, context)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


class Pager:
    def __init__(self, page: int, total: int, size: int):
        self.size = size
        self.total = total
        self.pages = max(1, math.ceil(total / size))
        self.page = min(max(1, page), self.pages)
        self.offset = (self.page - 1) * size
