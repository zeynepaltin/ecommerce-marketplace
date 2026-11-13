"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Login, logout and registration.
"""
from fastapi import APIRouter, Depends, Form, Request

from ..database import Database, DatabaseError, get_db
from ..repositories import AccountRepository, CustomerRepository
from ..security import PasswordHasher
from ..session import SessionManager
from ..web import redirect, render

router = APIRouter()
HOME_BY_ROLE = {"CUSTOMER": "/", "SELLER": "/seller", "ADMIN": "/admin"}


@router.get("/login")
def login_form(request: Request, next: str = ""):
    if SessionManager.user(request):
        return redirect(HOME_BY_ROLE[SessionManager.user(request)["role"]])
    return render(request, "login.html", next=next)


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form(""),
          db: Database = Depends(get_db)):
    account = AccountRepository(db).by_email(email.strip().lower())
    if not account or not PasswordHasher.verify(password, account["PasswordHash"]):
        SessionManager.flash(request, "Invalid e-mail address or password.", "danger")
        return render(request, "login.html", next=next, email=email)
    if account["UserStatus"] != "ACTIVE":
        SessionManager.flash(request, f"This account is {account['UserStatus'].lower()}. Please contact the administrator.", "danger")
        return render(request, "login.html", next=next, email=email)
    cart_count = CustomerRepository(db).cart_count(account["CustomerID"]) if account["Role"] == "CUSTOMER" else 0
    SessionManager.login(request, account, cart_count)
    SessionManager.flash(request, f"Welcome, {account['DisplayName']}!")
    target = next if next.startswith("/") and not next.startswith("//") else HOME_BY_ROLE[account["Role"]]
    return redirect(target)


@router.post("/logout")
def logout(request: Request):
    SessionManager.logout(request)
    SessionManager.flash(request, "You have been signed out.", "info")
    return redirect("/login")


@router.get("/register")
def register_form(request: Request):
    return render(request, "register.html", kind="customer")


@router.post("/register")
def register(request: Request, full_name: str = Form(...), email: str = Form(...), phone: str = Form(""),
             password: str = Form(...), password2: str = Form(...), db: Database = Depends(get_db)):
    form = {"full_name": full_name, "email": email, "phone": phone}
    if len(password) < 8 or password != password2:
        SessionManager.flash(request, "Passwords must match and contain at least 8 characters.", "danger")
        return render(request, "register.html", kind="customer", form=form)
    try:
        AccountRepository(db).register_customer(email.strip().lower(), PasswordHasher.hash(password), full_name.strip(), phone.strip())
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")
        return render(request, "register.html", kind="customer", form=form)
    SessionManager.flash(request, "Your account has been created. You can now sign in.")
    return redirect("/login")


@router.get("/register/seller")
def register_seller_form(request: Request):
    return render(request, "register.html", kind="seller")


@router.post("/register/seller")
def register_seller(request: Request, store_name: str = Form(...), email: str = Form(...), password: str = Form(...),
                    password2: str = Form(...), db: Database = Depends(get_db)):
    form = {"store_name": store_name, "email": email}
    if len(password) < 8 or password != password2:
        SessionManager.flash(request, "Passwords must match and contain at least 8 characters.", "danger")
        return render(request, "register.html", kind="seller", form=form)
    try:
        AccountRepository(db).register_seller(email.strip().lower(), PasswordHasher.hash(password), store_name.strip())
    except DatabaseError as e:
        SessionManager.flash(request, e.message, "danger")
        return render(request, "register.html", kind="seller", form=form)
    SessionManager.flash(request, "Your store has been registered and is waiting for administrator approval. You can sign in now.")
    return redirect("/login")
