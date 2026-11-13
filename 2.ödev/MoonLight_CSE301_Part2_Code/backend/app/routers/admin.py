"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Administrator pages: dashboard, users and stores, categories, orders, products.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request

from ..database import Database, DatabaseError, get_db
from ..repositories import AdminRepository, CatalogRepository, OrderRepository
from ..session import SessionManager, require_role, tracker
from ..web import Pager, redirect, render

router = APIRouter(prefix="/admin")
admin_only = require_role("ADMIN")
PAGE = 20


def run(request: Request, action, success: str):
    try:
        action()
        SessionManager.flash(request, success)
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")


def back(request: Request, default: str) -> str:
    ref = request.headers.get("referer", "")
    return ref if ref.startswith(str(request.base_url)) else default


@router.get("")
def dashboard(request: Request, user=Depends(admin_only), db: Database = Depends(get_db)):
    repo = AdminRepository(db)
    return render(request, "admin/dashboard.html", stats=repo.dashboard(), by_status=repo.orders_by_status(),
                  top=repo.top_sellers(5), online=tracker.online())


@router.get("/users")
def users(request: Request, role: str = "", status: str = "", q: str = "", page: int = 1,
          user=Depends(admin_only), db: Database = Depends(get_db)):
    repo = AdminRepository(db)
    pager = Pager(page, repo.count_users(role, status, q.strip()), PAGE)
    return render(request, "admin/users.html", users=repo.users(role, status, q.strip(), PAGE, pager.offset),
                  pager=pager, role=role, status=status, q=q)


@router.post("/users/{user_id}/status")
def set_user_status(request: Request, user_id: int, status: str = Form(...), user=Depends(admin_only),
                    db: Database = Depends(get_db)):
    run(request, lambda: AdminRepository(db).set_user_status(user["id"], user_id, status),
        f"Account #{user_id} is now {status.lower()}.")
    return redirect(back(request, "/admin/users"))


@router.post("/sellers/{seller_id}/status")
def set_seller_status(request: Request, seller_id: int, status: str = Form(...), user=Depends(admin_only),
                      db: Database = Depends(get_db)):
    run(request, lambda: AdminRepository(db).set_seller_status(seller_id, status),
        f"Store #{seller_id} is now {status.lower()}.")
    return redirect(back(request, "/admin/users?role=SELLER"))


@router.get("/categories")
def categories(request: Request, user=Depends(admin_only), db: Database = Depends(get_db)):
    return render(request, "admin/categories.html", categories=CatalogRepository(db).categories())


@router.post("/categories")
def add_category(request: Request, name: str = Form(...), description: str = Form(""), user=Depends(admin_only),
                 db: Database = Depends(get_db)):
    run(request, lambda: AdminRepository(db).add_category(name, description), f"Category '{name}' has been added.")
    return redirect("/admin/categories")


@router.post("/categories/{category_id}")
def update_category(request: Request, category_id: int, name: str = Form(...), description: str = Form(""),
                    user=Depends(admin_only), db: Database = Depends(get_db)):
    run(request, lambda: AdminRepository(db).update_category(category_id, name, description), "The category has been updated.")
    return redirect("/admin/categories")


@router.get("/orders")
def orders(request: Request, status: str = "", page: int = 1, user=Depends(admin_only), db: Database = Depends(get_db)):
    repo = AdminRepository(db)
    pager = Pager(page, repo.count_orders(status), PAGE)
    return render(request, "admin/orders.html", orders=repo.orders(status, PAGE, pager.offset), pager=pager, status=status)


@router.get("/orders/{order_id}")
def order_detail(request: Request, order_id: int, user=Depends(admin_only), db: Database = Depends(get_db)):
    repo = OrderRepository(db)
    header = repo.header(order_id, None)
    if not header:
        raise HTTPException(status_code=404, detail="Order not found")
    return render(request, "order_detail.html", order=header, items=repo.items(order_id),
                  payments=repo.payments(order_id), shipments=repo.shipments(order_id), admin_view=True)


@router.get("/products")
def products(request: Request, q: str = "", page: int = 1, user=Depends(admin_only), db: Database = Depends(get_db)):
    repo = AdminRepository(db)
    pager = Pager(page, repo.count_products(q.strip()), PAGE)
    return render(request, "admin/products.html", products=repo.products(q.strip(), PAGE, pager.offset), pager=pager, q=q)


@router.post("/products/{product_id}/status")
def set_product_status(request: Request, product_id: int, status: str = Form(...), user=Depends(admin_only),
                       db: Database = Depends(get_db)):
    run(request, lambda: AdminRepository(db).set_product_status(product_id, status), f"Product #{product_id} has been updated.")
    return redirect(back(request, "/admin/products"))
