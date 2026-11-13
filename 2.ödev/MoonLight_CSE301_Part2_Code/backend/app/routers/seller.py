"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Seller pages: dashboard, product and stock management, shipments.
"""
from decimal import Decimal, InvalidOperation
from itertools import groupby

from fastapi import APIRouter, Depends, Form, Request

from ..database import Database, DatabaseError, get_db
from ..repositories import CatalogRepository, SellerRepository
from ..session import SessionManager, require_role
from ..web import redirect, render

router = APIRouter(prefix="/seller")
seller_only = require_role("SELLER")


def to_price(text: str):
    try:
        return Decimal(text.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def run(request: Request, action, success: str):
    try:
        action()
        SessionManager.flash(request, success)
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")


@router.get("")
def dashboard(request: Request, user=Depends(seller_only), db: Database = Depends(get_db)):
    repo = SellerRepository(db)
    return render(request, "seller/dashboard.html", stats=repo.dashboard(user["seller_id"]),
                  top=repo.top_products(user["seller_id"], 5))


@router.get("/products")
def products(request: Request, user=Depends(seller_only), db: Database = Depends(get_db)):
    return render(request, "seller/products.html", products=SellerRepository(db).products(user["seller_id"]),
                  categories=CatalogRepository(db).categories())


@router.post("/products")
def add_product(request: Request, name: str = Form(...), category_id: int = Form(...), price: str = Form(...),
                quantity: int = Form(...), user=Depends(seller_only), db: Database = Depends(get_db)):
    run(request, lambda: SellerRepository(db).add_product(user["seller_id"], category_id, name, to_price(price), quantity),
        "The product has been added to your store.")
    return redirect("/seller/products")


@router.post("/products/{product_id}")
def update_product(request: Request, product_id: int, name: str = Form(...), category_id: int = Form(...),
                   price: str = Form(...), status: str = Form(...), user=Depends(seller_only), db: Database = Depends(get_db)):
    run(request, lambda: SellerRepository(db).update_product(user["seller_id"], product_id, name, to_price(price), category_id, status),
        "The product has been updated.")
    return redirect("/seller/products")


@router.post("/products/{product_id}/stock")
def update_stock(request: Request, product_id: int, quantity: int = Form(...), user=Depends(seller_only),
                 db: Database = Depends(get_db)):
    run(request, lambda: SellerRepository(db).update_stock(user["seller_id"], product_id, quantity),
        "The stock quantity has been updated.")
    return redirect("/seller/products")


@router.get("/orders")
def orders(request: Request, user=Depends(seller_only), db: Database = Depends(get_db)):
    rows = SellerRepository(db).pending_items(user["seller_id"])
    groups = [{"order": items[0], "lines": items} for _, g in groupby(rows, key=lambda r: r["OrderID"]) for items in [list(g)]]
    return render(request, "seller/orders.html", groups=groups)


@router.post("/orders/{order_id}/ship")
def create_shipment(request: Request, order_id: int, user=Depends(seller_only), db: Database = Depends(get_db)):
    run(request, lambda: SellerRepository(db).create_shipment(user["seller_id"], order_id),
        f"A shipment has been created for order #{order_id}. Add the tracking number when you hand it to the carrier.")
    return redirect("/seller/shipments")


@router.get("/shipments")
def shipments(request: Request, user=Depends(seller_only), db: Database = Depends(get_db)):
    return render(request, "seller/shipments.html", shipments=SellerRepository(db).shipments(user["seller_id"]))


@router.post("/shipments/{shipment_id}")
def update_shipment(request: Request, shipment_id: int, status: str = Form(...), tracking: str = Form(""),
                    user=Depends(seller_only), db: Database = Depends(get_db)):
    run(request, lambda: SellerRepository(db).update_shipment(user["seller_id"], shipment_id, status, tracking),
        f"Shipment #{shipment_id} is now {status.lower()}.")
    return redirect("/seller/shipments")
