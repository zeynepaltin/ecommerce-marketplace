"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Public pages: home, catalogue, product detail and the session overview page.
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import settings
from ..database import Database, get_db
from ..repositories import CatalogRepository
from ..session import SessionManager, require_role
from ..web import Pager, render

router = APIRouter()
SORTS = {"": "Newest", "price_asc": "Price: low to high", "price_desc": "Price: high to low", "rating": "Best rated"}


@router.get("/")
def home(request: Request, db: Database = Depends(get_db)):
    repo = CatalogRepository(db)
    categories = sorted(repo.categories(), key=lambda c: c["ProductCount"], reverse=True)[:8]
    recent = [p for p in (repo.product(pid) for pid in request.session.get("recent_products", [])) if p]
    return render(request, "home.html", categories=categories, latest=repo.browse(None, "", "", 8, 0),
                  top_rated=repo.browse(None, "", "rating", 4, 0), recent=recent)


@router.get("/products")
def products(request: Request, category: int | None = None, q: str = "", sort: str = "", page: int = 1,
             db: Database = Depends(get_db)):
    repo = CatalogRepository(db)
    sort = sort if sort in SORTS else ""
    pager = Pager(page, repo.count(category, q.strip()), settings.page_size)
    items = repo.browse(category, q.strip(), sort, pager.size, pager.offset)
    categories = repo.categories()
    current = next((c for c in categories if c["CategoryID"] == category), None)
    return render(request, "products.html", products=items, categories=categories, current=current,
                  q=q, sort=sort, sorts=SORTS, pager=pager, category=category)


@router.get("/products/{product_id}")
def product_detail(request: Request, product_id: int, db: Database = Depends(get_db)):
    repo = CatalogRepository(db)
    product = repo.product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    SessionManager.remember_product(request, product_id)
    return render(request, "product_detail.html", product=product, reviews=repo.reviews(product_id))


@router.get("/account")
def account(request: Request, user: dict = Depends(require_role())):
    return render(request, "account.html")
