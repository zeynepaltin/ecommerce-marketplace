"""CSE 301 - Moon Light - Part 2 end-to-end web tests.

Drives the web application through the complete multi-vendor workflow for all
three roles with FastAPI's TestClient (requires a freshly initialised database).

Group members: Mehmet Çolaker (220610028), Emre Sefa Kazan (230610019),
Ahmet Yasin Akyüz (230610015), Hüseyin Gürses (230610029),
Zeynep Sümeyra Altın (230610005), Ulaş Budak (25060902060)

Usage (from the repository root):  python tests/test_web.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import session as session_module  # noqa: E402
from backend.app.config import Settings  # noqa: E402
from backend.app.main import app  # noqa: E402

PW = "Demo1234!"
results = []


def check(name, cond):
    results.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")


def client():
    return TestClient(app, follow_redirects=True)


def login(c, email, password=PW):
    return c.post("/login", data={"email": email, "password": password})


def main():
    # ---------- anonymous visitor ----------
    c = client()
    for url in ["/", "/products", "/products?category=1&sort=price_asc", "/products?q=Laptop&page=1", "/products/1", "/login", "/register", "/register/seller"]:
        check(f"GET {url} -> 200", c.get(url).status_code == 200)
    r = c.get("/cart")
    check("protected page redirects anonymous user to login", r.url.path == "/login" and "Please sign in" in r.text)
    check("unknown product -> 404 page", c.get("/products/999999").status_code == 404)
    r = login(c, "admin01@moonlightmarket.com", "wrong-password")
    check("wrong password rejected", "Invalid e-mail address or password" in r.text)
    r = login(c, "nobody@example.com")
    check("unknown e-mail rejected", "Invalid e-mail address or password" in r.text)

    # ---------- registration and customer flow ----------
    r = c.post("/register", data={"full_name": "Web Test", "email": "web.test@example.com", "phone": "", "password": "Secret123", "password2": "Secret123"})
    check("customer registration", "account has been created" in r.text)
    r = c.post("/register", data={"full_name": "Web Test", "email": "web.test@example.com", "phone": "", "password": "Secret123", "password2": "Secret123"})
    check("duplicate registration shows DB message", "already registered" in r.text)
    r = login(c, "web.test@example.com", "Secret123")
    check("customer login", "Welcome, Web Test" in r.text)
    check("customer cannot open admin pages (403)", "do not have permission" in c.get("/admin").text)
    r = c.get("/checkout")
    check("empty cart cannot check out", r.url.path == "/cart" and "cart is empty" in r.text)
    c.post("/addresses", data={"city": "İzmir", "district": "Bornova", "address_line": "Kazımdirik Mah. 372 Sok. No:5"})
    check("address saved", "Bornova" in c.get("/addresses").text)

    # two products from two different sellers
    page = c.get("/products?sort=price_asc").text
    ids = [int(x) for x in dict.fromkeys(re.findall(r'href="/products/(\d+)"', page))]
    chosen, sellers = [], set()
    for pid in ids:
        html = c.get(f"/products/{pid}").text
        store = re.search(r"Sold and shipped by <strong>(.*?)</strong>", html).group(1)
        if "Add to cart" in html and store not in sellers:
            chosen.append((pid, store)); sellers.add(store)
        if len(chosen) == 2:
            break
    for pid, _ in chosen:
        r = c.post("/cart/add", data={"product_id": pid, "quantity": 1, "next": f"/products/{pid}"})
    check("products added; cart badge from session", "added to your cart" in r.text and 'cart-badge">2<' in r.text)
    r = c.post("/cart/update", data={"product_id": chosen[0][0], "quantity": 2})
    check("cart quantity updated", "cart has been updated" in r.text and 'cart-badge">3<' in r.text)
    check("too large quantity rejected by procedure", "exceeds the available stock" in c.post("/cart/update", data={"product_id": chosen[0][0], "quantity": 100000}).text)
    r = c.get("/checkout")
    check("checkout page lists 2 stores", "from 2 store(s)" in r.text)
    addr_id = re.search(r'name="address_id" id="a\d+" value="(\d+)"', r.text).group(1)
    r = c.post("/checkout", data={"address_id": addr_id, "method": "CREDIT_CARD"})
    m = re.search(r"Order #(\d+) has been placed", r.text)
    check("order placed and order page shown", m is not None and "PROCESSING" in r.text)
    order_id = int(m.group(1))
    check("cart badge cleared after checkout", "cart-badge" not in r.text)
    check("order appears in history", f"/orders/{order_id}" in c.get("/orders").text)
    check("account page shows session variables and history", "Last order" in (acc := c.get("/account").text) and "Order detail" in acc)

    # ---------- sellers ship their parts ----------
    from backend.app.database import Database
    db = Database()
    seller_emails = {}
    for pid, store in chosen:
        seller_emails[store] = db.one("sp_admin_list_users", "SELLER", "", store, 1, 0)["Email"]
    db.close()
    for n, (store, email) in enumerate(seller_emails.items(), 1):
        s = client()
        r = login(s, email)
        check(f"seller {n} login -> dashboard", "seller dashboard" in r.text)
        r = s.get("/seller/orders")
        check(f"seller {n} sees order #{order_id} to ship", f"Order #{order_id}" in r.text)
        r = s.post(f"/seller/orders/{order_id}/ship")
        check(f"seller {n} created shipment", "A shipment has been created" in r.text)
        sh_id = re.findall(r'action="/seller/shipments/(\d+)"', r.text)[0]
        check(f"seller {n} tracking number required", "tracking number is required" in s.post(f"/seller/shipments/{sh_id}", data={"status": "SHIPPED", "tracking": " "}).text)
        r = s.post(f"/seller/shipments/{sh_id}", data={"status": "SHIPPED", "tracking": f"YK{order_id}{n:03d}"})
        check(f"seller {n} marked shipment shipped", "is now shipped" in r.text)
        if n == 1:
            check("customer cannot cancel after a shipment left", "can no longer be cancelled" in c.post(f"/orders/{order_id}/cancel").text)
            check("order still PROCESSING while second store has not shipped", "PROCESSING" in c.get(f"/orders/{order_id}").text)
        r = s.post(f"/seller/shipments/{sh_id}", data={"status": "DELIVERED"})
        check(f"seller {n} marked shipment delivered", "is now delivered" in r.text)
        for url in ["/seller", "/seller/products", "/seller/shipments"]:
            check(f"seller {n} GET {url}", s.get(url).status_code == 200)
    r = c.get(f"/orders/{order_id}")
    check("order DELIVERED after both shipments (trigger)", re.search(r"Order #\d+ <span class=\"badge text-bg-success\">DELIVERED", r.text) is not None)
    r = c.get("/reviews")
    check("delivered products offered for review", all(f'value="{pid}"' in r.text for pid, _ in chosen))
    r = c.post("/reviews", data={"product_id": chosen[0][0], "rating": 5, "comment": "Arrived quickly, works great."})
    check("review saved", "Thank you for your review" in r.text)
    check("review visible on product page", "Arrived quickly, works great." in c.get(f"/products/{chosen[0][0]}").text)

    # cancel flow
    c.post("/cart/add", data={"product_id": chosen[1][0], "quantity": 1})
    r = c.post("/checkout", data={"address_id": addr_id, "method": "DIGITAL_WALLET"})
    oid2 = int(re.search(r"Order #(\d+) has been placed", r.text).group(1))
    r = c.post(f"/orders/{oid2}/cancel")
    check("unshipped order cancelled and refunded", "has been cancelled" in r.text and "REFUNDED" in r.text)
    check("other customer's order is not visible", c.get("/orders/1").status_code == 404)

    # ---------- pending seller and admin ----------
    p = client()
    r = p.post("/register/seller", data={"store_name": "Web Test Store", "email": "web.store@example.com", "password": "Secret123", "password2": "Secret123"})
    check("seller registration", "waiting for administrator approval" in r.text)
    login(p, "web.store@example.com", "Secret123")
    r = p.post("/seller/products", data={"name": "Test Lamp", "category_id": 1, "price": "199.90", "quantity": 5})
    check("pending store cannot list products", "must be approved" in r.text)

    a = client()
    r = login(a, "admin01@moonlightmarket.com")
    check("admin login -> dashboard", "Platform overview" in r.text)
    check("admin sees online users and their current page", "web.test@example.com" in r.text and "web.store@example.com" in r.text)
    r = a.get("/admin/users?role=SELLER&status=PENDING&q=Web Test Store")
    sid = re.search(r'action="/admin/sellers/(\d+)/status"', r.text).group(1)
    r = a.post(f"/admin/sellers/{sid}/status", data={"status": "ACTIVE"}, headers={"referer": "http://testserver/admin/users?role=SELLER"})
    check("admin approved store", f"Store #{sid} is now active" in r.text)
    p.post("/logout"); login(p, "web.store@example.com", "Secret123")
    r = p.post("/seller/products", data={"name": "Test Lamp", "category_id": 1, "price": "199,90", "quantity": 5})
    check("approved store lists a product", "has been added" in r.text and "Test Lamp" in r.text)
    new_pid = re.search(r'action="/seller/products/(\d+)/stock"', r.text).group(1)
    r = p.post(f"/seller/products/{new_pid}/stock", data={"quantity": 0})
    check("stock 0 -> OUT OF STOCK (trigger)", "OUT OF STOCK" in r.text)
    r = a.post("/admin/categories", data={"name": "Web Test Category", "description": "created by test"})
    check("admin added category", "Web Test Category" in r.text)
    for url in ["/admin/users", "/admin/users?role=CUSTOMER&page=3", "/admin/orders", "/admin/orders?status=CANCELLED", f"/admin/orders/{order_id}", "/admin/products?q=Lamp", "/admin/categories"]:
        check(f"admin GET {url}", a.get(url).status_code == 200)
    r = a.post(f"/admin/products/{new_pid}/status", data={"status": "INACTIVE"})
    check("admin withdrew product", "has been updated" in r.text)
    uid = re.search(r'action="/admin/users/(\d+)/status"', a.get("/admin/users?q=web.test@example.com").text).group(1)
    a.post(f"/admin/users/{uid}/status", data={"status": "SUSPENDED"})
    c.post("/logout")
    check("suspended account cannot sign in", "This account is suspended" in login(c, "web.test@example.com", "Secret123").text)

    # ---------- idle timeout ----------
    t = client()
    login(t, "seda.korkmaz@hotmail.com")
    original = session_module.settings
    session_module.settings = Settings(session_idle_minutes=-1)
    r = t.get("/orders")
    session_module.settings = original
    check("idle session expires and redirects to login", r.url.path == "/login" and "session expired" in r.text)
    r = login(t, "seda.korkmaz@hotmail.com")
    t.post("/logout")
    check("logout clears session", t.get("/orders").url.path == "/login")

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
