"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Customer pages: cart, checkout, orders, addresses and reviews.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request

from ..database import Database, DatabaseError, get_db
from ..repositories import CustomerRepository, OrderRepository
from ..session import SessionManager, require_role
from ..web import redirect, render

router = APIRouter()
customer_only = require_role("CUSTOMER")
METHODS = {"CREDIT_CARD": "Credit card", "DEBIT_CARD": "Debit card", "BANK_TRANSFER": "Bank transfer", "DIGITAL_WALLET": "Digital wallet"}


def safe_next(url: str, default: str) -> str:
    return url if url.startswith("/") and not url.startswith("//") else default


@router.get("/cart")
def cart(request: Request, user=Depends(customer_only), db: Database = Depends(get_db)):
    items = CustomerRepository(db).cart(user["customer_id"])
    request.session["cart_count"] = sum(i["Quantity"] for i in items)
    return render(request, "cart.html", items=items, total=sum(i["LineTotal"] for i in items))


@router.post("/cart/add")
def cart_add(request: Request, product_id: int = Form(...), quantity: int = Form(1), next: str = Form("/cart"),
             user=Depends(customer_only), db: Database = Depends(get_db)):
    try:
        request.session["cart_count"] = CustomerRepository(db).cart_add(user["customer_id"], product_id, quantity)
        SessionManager.flash(request, "The product has been added to your cart.")
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")
    return redirect(safe_next(next, "/cart"))


@router.post("/cart/update")
def cart_update(request: Request, product_id: int = Form(...), quantity: int = Form(...),
                user=Depends(customer_only), db: Database = Depends(get_db)):
    try:
        request.session["cart_count"] = CustomerRepository(db).cart_update(user["customer_id"], product_id, quantity)
        SessionManager.flash(request, "Your cart has been updated." if quantity > 0 else "The product has been removed from your cart.")
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")
    return redirect("/cart")


@router.get("/checkout")
def checkout_form(request: Request, user=Depends(customer_only), db: Database = Depends(get_db)):
    repo = CustomerRepository(db)
    items = repo.cart(user["customer_id"])
    if not items:
        SessionManager.flash(request, "Your cart is empty.", "warning")
        return redirect("/cart")
    return render(request, "checkout.html", items=items, total=sum(i["LineTotal"] for i in items),
                  addresses=repo.addresses(user["customer_id"]), methods=METHODS)


@router.post("/checkout")
def checkout(request: Request, address_id: int = Form(...), method: str = Form(...),
             user=Depends(customer_only), db: Database = Depends(get_db)):
    try:
        order = CustomerRepository(db).place_order(user["customer_id"], address_id, method)
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")
        return redirect("/checkout")
    request.session["cart_count"] = 0
    request.session["last_order_id"] = order["OrderID"]
    SessionManager.flash(request, f"Thank you! Order #{order['OrderID']} has been placed and paid.")
    return redirect(f"/orders/{order['OrderID']}")


@router.get("/orders")
def orders(request: Request, user=Depends(customer_only), db: Database = Depends(get_db)):
    return render(request, "orders.html", orders=CustomerRepository(db).orders(user["customer_id"]))


@router.get("/orders/{order_id}")
def order_detail(request: Request, order_id: int, user=Depends(customer_only), db: Database = Depends(get_db)):
    repo = OrderRepository(db)
    header = repo.header(order_id, user["customer_id"])
    if not header:
        raise HTTPException(status_code=404, detail="Order not found")
    return render(request, "order_detail.html", order=header, items=repo.items(order_id),
                  payments=repo.payments(order_id), shipments=repo.shipments(order_id), admin_view=False)


@router.post("/orders/{order_id}/cancel")
def cancel_order(request: Request, order_id: int, user=Depends(customer_only), db: Database = Depends(get_db)):
    try:
        CustomerRepository(db).cancel_order(user["customer_id"], order_id)
        SessionManager.flash(request, f"Order #{order_id} has been cancelled and the payment refunded.")
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")
    return redirect(f"/orders/{order_id}")


@router.get("/addresses")
def addresses(request: Request, user=Depends(customer_only), db: Database = Depends(get_db)):
    return render(request, "addresses.html", addresses=CustomerRepository(db).addresses(user["customer_id"]))


@router.post("/addresses")
def add_address(request: Request, city: str = Form(...), district: str = Form(...), address_line: str = Form(...),
                next: str = Form("/addresses"), user=Depends(customer_only), db: Database = Depends(get_db)):
    try:
        CustomerRepository(db).add_address(user["customer_id"], city, district, address_line)
        SessionManager.flash(request, "The address has been saved.")
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")
    return redirect(safe_next(next, "/addresses"))


@router.get("/reviews")
def reviews(request: Request, user=Depends(customer_only), db: Database = Depends(get_db)):
    return render(request, "reviews.html", items=CustomerRepository(db).reviewable(user["customer_id"]))


@router.post("/reviews")
def add_review(request: Request, product_id: int = Form(...), rating: int = Form(...), comment: str = Form(""),
               user=Depends(customer_only), db: Database = Depends(get_db)):
    try:
        CustomerRepository(db).add_review(user["customer_id"], product_id, rating, comment)
        SessionManager.flash(request, "Thank you for your review!")
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")
    return redirect("/reviews")
