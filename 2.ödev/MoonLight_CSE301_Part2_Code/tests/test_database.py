"""CSE 301 - Moon Light - Part 2 database tests.

Exercises every stored procedure and every trigger against a freshly
initialised database (Part 1 SQL + Part 2 SQL) and prints PASS / FAIL.

Group members: Mehmet Çolaker (220610028), Emre Sefa Kazan (230610019),
Ahmet Yasin Akyüz (230610015), Hüseyin Gürses (230610029),
Zeynep Sümeyra Altın (230610005), Ulaş Budak (25060902060)

Usage:  python tests/test_database.py   (reads DB_* settings from .env)
"""
import os
import sys

import pymysql
import pymysql.cursors

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CONN = dict(host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "ecommerce_marketplace"), charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor, autocommit=True)

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not cond else ""))


class DB:
    def __init__(self):
        self.conn = pymysql.connect(**CONN)

    def call(self, proc, *args):
        with self.conn.cursor() as cur:
            cur.callproc(proc, args)
            rows = cur.fetchall()
            while cur.nextset():
                pass
            return list(rows)

    def one(self, proc, *args):
        rows = self.call(proc, *args)
        return rows[0] if rows else None

    def q(self, sql, *args):  # direct SQL is used only to inspect results in tests
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()

    def fails(self, proc, *args):
        try:
            self.call(proc, *args)
            return None
        except pymysql.err.MySQLError as e:
            return e.args[1] if len(e.args) > 1 else str(e)


def main():
    db = DB()
    H = "$2b$10$abcdefghijklmnopqrstuuJ6o7Yb6v0m1W5o5xw5pK2bqk7uHn2pW"

    # ---------- A. accounts ----------
    u = db.one("sp_get_user_by_email", "admin01@moonlightmarket.com")
    check("A1 sp_get_user_by_email returns admin", u and u["Role"] == "ADMIN" and u["DisplayName"] == "Administrator")
    r = db.one("sp_register_customer", "test.customer@example.com", H, "Test Customer", "+90 555 000 00 00")
    cust = r["CustomerID"]
    check("A2 sp_register_customer creates Users + Customer", cust and db.one("sp_get_user_by_email", "test.customer@example.com")["CustomerID"] == cust)
    check("A2 duplicate e-mail rejected", "already registered" in (db.fails("sp_register_customer", "test.customer@example.com", H, "X", "") or ""))
    r = db.one("sp_register_seller", "test.seller@example.com", H, "Test Store")
    seller = r["SellerID"]
    check("A3 sp_register_seller creates PENDING store", db.q("SELECT Status FROM Seller WHERE SellerID=%s", seller)[0]["Status"] == "PENDING")

    # ---------- T1/T2 role triggers ----------
    admin_uid = u["UserID"]
    try:
        db.q("INSERT INTO Customer (UserID, FullName) VALUES (%s, 'Wrong')", admin_uid); ok = False
    except pymysql.err.MySQLError as e:
        ok = "role CUSTOMER" in e.args[1]
    check("T1 trg_customer_before_insert blocks profile on ADMIN account", ok)
    try:
        db.q("INSERT INTO Seller (UserID, StoreName, Status) VALUES (%s, 'Wrong', 'PENDING')", admin_uid); ok = False
    except pymysql.err.MySQLError as e:
        ok = "role SELLER" in e.args[1]
    check("T2 trg_seller_before_insert blocks profile on ADMIN account", ok)

    # ---------- B. catalogue ----------
    cats = db.call("sp_list_categories")
    check("B1 sp_list_categories", len(cats) == 117)
    page = db.call("sp_browse_products", None, "", "price_asc", 12, 0)
    check("B2 sp_browse_products returns one page sorted by price", len(page) == 12 and all(page[i]["Price"] <= page[i + 1]["Price"] for i in range(11)))
    total = db.one("sp_count_products", None, "")["Total"]
    allp = db.call("sp_browse_products", None, "", "", 1000, 0)
    check("B3 sp_count_products matches browse result", total == len(allp), f"{total} vs {len(allp)}")
    cat_id = page[0]["CategoryName"]
    pid = next(p["ProductID"] for p in allp if p["Status"] == "ACTIVE" and p["Stock"] >= 5)
    d = db.one("sp_get_product_detail", pid)
    check("B4 sp_get_product_detail", d and d["ProductID"] == pid and d["StoreName"])
    revs = db.call("sp_get_product_reviews", pid)
    check("B5 sp_get_product_reviews", isinstance(revs, list))

    # ---------- C. cart / addresses ----------
    check("C6 address required fields", "required" in (db.fails("sp_add_address", cust, "", "x", "y") or ""))
    addr = db.one("sp_add_address", cust, "İstanbul", "Kadıköy", "Moda Mah. Test Sok. No:1")["AddressID"]
    check("C5 sp_list_addresses", len(db.call("sp_list_addresses", cust)) == 1)
    stock_before = d["Stock"]
    cnt = db.one("sp_cart_add", cust, pid, 2)["CartCount"]
    check("C3 sp_cart_add creates cart and adds line", cnt == 2)
    check("C3 stock limit enforced", "exceeds" in (db.fails("sp_cart_add", cust, pid, stock_before) or ""))
    other = next(p for p in allp if p["Status"] == "ACTIVE" and p["Stock"] >= 3 and p["ProductID"] != pid)
    db.call("sp_cart_add", cust, other["ProductID"], 1)
    cnt = db.one("sp_cart_update", cust, other["ProductID"], 3)["CartCount"]
    check("C4 sp_cart_update changes quantity", cnt == 5)
    cart = db.call("sp_get_cart", cust)
    check("C1 sp_get_cart", len(cart) == 2 and sum(c["Quantity"] for c in cart) == 5)
    check("C2 sp_get_cart_count", db.one("sp_get_cart_count", cust)["CartCount"] == 5)
    oos = db.q("SELECT ProductID FROM Product WHERE Status='OUT_OF_STOCK' LIMIT 1")[0]["ProductID"]
    check("C3 unavailable product rejected", "not available" in (db.fails("sp_cart_add", cust, oos, 1) or ""))

    # ---------- T3 address ownership ----------
    foreign_addr = db.q("SELECT AddressID FROM Address WHERE CustomerID <> %s LIMIT 1", cust)[0]["AddressID"]
    check("T3 trg_orders_before_insert rejects foreign address", "does not belong" in (db.fails("sp_place_order", cust, foreign_addr, "CREDIT_CARD") or ""))
    check("D1 invalid payment method rejected", "valid payment" in (db.fails("sp_place_order", cust, addr, "CASH") or ""))
    check("D1 cart kept after failed checkout", db.one("sp_get_cart_count", cust)["CartCount"] == 5)

    # ---------- D. checkout + T4/T5/T7 ----------
    price_pid = d["Price"]; price_other = other["Price"]; stock_other = other["Stock"]
    o = db.one("sp_place_order", cust, addr, "CREDIT_CARD")
    oid = o["OrderID"]
    expected = price_pid * 2 + price_other * 3
    check("D1 sp_place_order returns order and total", o["TotalAmount"] == expected, f"{o['TotalAmount']} vs {expected}")
    check("T5 trg_orderitem_after_insert deducts stock once",
          db.one("sp_get_product_detail", pid)["Stock"] == stock_before - 2 and db.one("sp_get_product_detail", other["ProductID"])["Stock"] == stock_other - 3)
    items = db.call("sp_get_order_items", oid)
    check("T4 trg_orderitem_before_insert sets purchase-time unit price", {i["ProductID"]: i["UnitPrice"] for i in items} == {pid: price_pid, other["ProductID"]: price_other})
    check("D1 cart emptied after checkout", db.one("sp_get_cart_count", cust)["CartCount"] == 0)
    hdr = db.one("sp_get_order_header", oid, cust)
    check("D3 sp_get_order_header (owner)", hdr and hdr["Status"] == "PROCESSING" and hdr["Email"] == "test.customer@example.com")
    check("D3 sp_get_order_header hides other customers' orders", db.one("sp_get_order_header", oid, 1) is None)
    pays = db.call("sp_get_order_payments", oid)
    check("D5 sp_get_order_payments", len(pays) == 1 and pays[0]["Status"] == "COMPLETED" and pays[0]["Amount"] == expected)
    hist = db.call("sp_get_customer_orders", cust)
    check("D2 sp_get_customer_orders", len(hist) == 1 and hist[0]["ItemCount"] == 5)

    # insufficient stock via trigger T4
    db.call("sp_seller_update_stock", d["SellerID"], pid, 1)
    db.call("sp_cart_add", cust, pid, 1)
    db.call("sp_seller_update_stock", d["SellerID"], pid, 0)
    st = db.one("sp_get_product_detail", pid)["Status"]
    check("T7 trg_inventory_before_update sets OUT_OF_STOCK at zero", st == "OUT_OF_STOCK")
    msg = db.fails("sp_place_order", cust, addr, "DEBIT_CARD")
    check("T4 checkout rejected for unavailable product (transaction rolled back)", msg and "no longer available" in msg and db.one("sp_count_products", None, "")["Total"] == total)
    db.call("sp_seller_update_stock", d["SellerID"], pid, stock_before - 2)
    check("T7 product re-activated when stock returns", db.one("sp_get_product_detail", pid)["Status"] == "ACTIVE")
    db.call("sp_cart_update", cust, pid, 0)

    # ---------- E. seller flow + T8/T9 ----------
    s1 = d["SellerID"]
    pend = db.call("sp_seller_pending_items", s1)
    check("E7 sp_seller_pending_items lists new order", any(r["OrderID"] == oid for r in pend))
    sh = db.one("sp_seller_create_shipment", s1, oid)["ShipmentID"]
    check("E8 sp_seller_create_shipment", sh and not any(r["OrderID"] == oid for r in db.call("sp_seller_pending_items", s1)))
    check("E8 second shipment for same items rejected", "no items" in (db.fails("sp_seller_create_shipment", s1, oid) or ""))
    foreign_item = db.q("SELECT OrderItemID FROM OrderItem WHERE OrderID <> %s LIMIT 1", oid)[0]["OrderItemID"]
    try:
        db.q("INSERT INTO ShipmentItem (ShipmentID, OrderItemID) VALUES (%s, %s)", sh, foreign_item); ok = False
    except pymysql.err.MySQLError as e:
        ok = "own seller" in e.args[1] or "Duplicate" in e.args[1]
    check("T8 trg_shipmentitem_before_insert blocks foreign order item", ok)
    check("E10 tracking number required", "tracking number" in (db.fails("sp_seller_update_shipment", s1, sh, "SHIPPED", "") or ""))
    check("E10 invalid transition rejected", "Invalid" in (db.fails("sp_seller_update_shipment", s1, sh, "DELIVERED", "") or ""))
    db.call("sp_seller_update_shipment", s1, sh, "SHIPPED", "YK99999999999")
    s2 = db.q("SELECT p.SellerID FROM Product p WHERE p.ProductID=%s", other["ProductID"])[0]["SellerID"]
    if s2 != s1:
        check("T9 order stays PROCESSING while another seller has not shipped", db.one("sp_get_order_header", oid, cust)["Status"] == "PROCESSING")
        check("D7 cancellation blocked after a shipment is shipped", "already been shipped" in (db.fails("sp_cancel_order", cust, oid) or ""))
        sh2 = db.one("sp_seller_create_shipment", s2, oid)["ShipmentID"]
        db.call("sp_seller_update_shipment", s2, sh2, "SHIPPED", "AR12345678901")
    check("T9 trg_shipment_after_update sets order SHIPPED", db.one("sp_get_order_header", oid, cust)["Status"] == "SHIPPED")
    ships = db.call("sp_get_order_shipments", oid)
    check("D6 sp_get_order_shipments (one per seller)", len(ships) == (2 if s2 != s1 else 1))
    for s in ships:
        sid = db.q("SELECT SellerID FROM Shipment WHERE ShipmentID=%s", s["ShipmentID"])[0]["SellerID"]
        db.call("sp_seller_update_shipment", sid, s["ShipmentID"], "DELIVERED", "")
    check("T9 order DELIVERED when all shipments delivered", db.one("sp_get_order_header", oid, cust)["Status"] == "DELIVERED")
    check("E9 sp_seller_shipments", any(r["ShipmentID"] == sh for r in db.call("sp_seller_shipments", s1)))

    # ---------- D8/D9 reviews + T10 ----------
    rv = db.call("sp_get_reviewable_items", cust)
    check("D8 sp_get_reviewable_items", {r["ProductID"] for r in rv} == {pid, other["ProductID"]})
    db.call("sp_add_review", cust, pid, 5, "Great product")
    check("D9 sp_add_review", len(db.call("sp_get_reviewable_items", cust)) == 1)
    never = db.q("SELECT ProductID FROM Product WHERE ProductID NOT IN (%s, %s) LIMIT 1", pid, other["ProductID"])[0]["ProductID"]
    check("T10 trg_review_before_insert rejects review without delivery", "delivered to you" in (db.fails("sp_add_review", cust, never, 4, "x") or ""))
    check("CHECK constraint rejects rating 6", db.fails("sp_add_review", cust, other["ProductID"], 6, "x") is not None)

    # ---------- D7 cancellation + T6 ----------
    db.call("sp_cart_add", cust, other["ProductID"], 1)
    stock_o = db.one("sp_get_product_detail", other["ProductID"])["Stock"]
    oid2 = db.one("sp_place_order", cust, addr, "DIGITAL_WALLET")["OrderID"]
    db.call("sp_cancel_order", cust, oid2)
    check("D7 sp_cancel_order sets CANCELLED and refunds", db.one("sp_get_order_header", oid2, cust)["Status"] == "CANCELLED"
          and db.call("sp_get_order_payments", oid2)[0]["Status"] == "REFUNDED")
    check("T6 trg_orders_after_update restores stock", db.one("sp_get_product_detail", other["ProductID"])["Stock"] == stock_o)
    check("D7 cancelling twice rejected", "Only pending" in (db.fails("sp_cancel_order", cust, oid2) or ""))

    # ---------- E. seller catalogue ----------
    check("E4 pending store cannot list products", "approved" in (db.fails("sp_seller_add_product", seller, 1, "X", 10, 5) or ""))
    db.call("sp_admin_set_seller_status", seller, "ACTIVE")
    np = db.one("sp_seller_add_product", seller, 1, "Test Phone", 999.90, 4)["ProductID"]
    check("E4 sp_seller_add_product creates Product + Inventory", db.one("sp_get_product_detail", np)["Stock"] == 4)
    db.call("sp_seller_update_product", seller, np, "Test Phone 2", 1099.90, 2, "ACTIVE")
    check("E5 sp_seller_update_product", db.one("sp_get_product_detail", np)["ProductName"] == "Test Phone 2")
    check("E5 foreign product rejected", "not found" in (db.fails("sp_seller_update_product", s1, np, "x", 10, 1, "ACTIVE") or ""))
    check("E3 sp_seller_products", len(db.call("sp_seller_products", seller)) == 1)
    dash = db.one("sp_seller_dashboard", s1)
    check("E1 sp_seller_dashboard", dash and dash["ProductCount"] > 0 and dash["Revenue"] > 0)
    check("E2 sp_seller_top_products", len(db.call("sp_seller_top_products", s1, 5)) > 0)

    # ---------- F. admin ----------
    check("F1 sp_admin_dashboard", db.one("sp_admin_dashboard")["Customers"] == 131)
    check("F2 sp_admin_orders_by_status", sum(r["OrderCount"] for r in db.call("sp_admin_orders_by_status")) == 232)
    check("F3 sp_admin_top_sellers", len(db.call("sp_admin_top_sellers", 5)) == 5)
    lu = db.call("sp_admin_list_users", "SELLER", "", "", 20, 0)
    check("F4/F5 user list and count", len(lu) == 20 and db.one("sp_admin_count_users", "SELLER", "", "")["Total"] == 111)
    check("F6 admin cannot change own status", "own account" in (db.fails("sp_admin_set_user_status", admin_uid, admin_uid, "SUSPENDED") or ""))
    seller_uid = db.q("SELECT UserID FROM Seller WHERE SellerID=%s", seller)[0]["UserID"]
    db.call("sp_admin_set_user_status", admin_uid, seller_uid, "SUSPENDED")
    check("F6 + T11 suspending a seller account suspends store and withdraws products",
          db.q("SELECT Status FROM Seller WHERE SellerID=%s", seller)[0]["Status"] == "SUSPENDED"
          and db.one("sp_get_product_detail", np)["Status"] == "INACTIVE")
    db.call("sp_admin_set_seller_status", seller, "ACTIVE")
    check("F7 sp_admin_set_seller_status re-activates account", db.q("SELECT Status FROM Users WHERE UserID=%s", seller_uid)[0]["Status"] == "ACTIVE")
    cid = db.one("sp_admin_add_category", "Test Category", "desc")["CategoryID"]
    check("F8 duplicate category rejected", "already exists" in (db.fails("sp_admin_add_category", "Test Category", "") or ""))
    db.call("sp_admin_update_category", cid, "Test Category 2", "")
    check("F9 sp_admin_update_category", any(c["CategoryName"] == "Test Category 2" for c in db.call("sp_list_categories")))
    check("F10/F11 order list and count", len(db.call("sp_admin_list_orders", "DELIVERED", 10, 0)) == 10 and db.one("sp_admin_count_orders", "")["Total"] == 232)
    check("F12/F13 product list and count", len(db.call("sp_admin_list_products", "", 10, 0)) == 10 and db.one("sp_admin_count_products", "")["Total"] == 321)
    db.call("sp_admin_set_product_status", np, "ACTIVE")
    check("F14 sp_admin_set_product_status", db.one("sp_get_product_detail", np)["Status"] == "ACTIVE")

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
