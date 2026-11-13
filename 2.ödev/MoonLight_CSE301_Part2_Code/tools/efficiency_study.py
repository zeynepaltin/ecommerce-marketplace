"""CSE 301 - Moon Light - Part 2 efficiency study (data traffic).

Compares, for five typical pages/operations, a naive data-access strategy with
the stored-procedure strategy used by the application. For each strategy it
measures, using MySQL's own session counters:
  * bytes sent by the server to the application (Bytes_sent),
  * bytes sent by the application to the server (Bytes_received),
  * number of client/server round trips (statements sent),
  * rows read by the server (sum of Handler_read_* counters),
  * rows delivered to the application,
  * mean wall-clock time per execution.

Group members: Mehmet Çolaker (220610028), Emre Sefa Kazan (230610019),
Ahmet Yasin Akyüz (230610015), Hüseyin Gürses (230610029),
Zeynep Sümeyra Altın (230610005), Ulaş Budak (25060902060)

Usage (fresh database recommended; E5 creates orders):
    python tools/efficiency_study.py            -> prints a table, writes tools/efficiency_results.json
Re-run the Part 1 and Part 2 SQL files afterwards to restore the initial data.
"""
import json
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path

import pymysql
import pymysql.cursors

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

RUNS = 30


def connect():
    return pymysql.connect(host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3306")),
                           user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""),
                           database=os.getenv("DB_NAME", "ecommerce_marketplace"), charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor, autocommit=True)


class Meter:
    """Executes statements and counts round trips and rows returned to the client."""

    def __init__(self, conn):
        self.conn = conn
        self.trips = 0
        self.rows = 0

    def run(self, sql, args=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            self.trips += 1
            out = list(cur.fetchall())
            self.rows += len(out)
            while cur.nextset():
                pass
            return out

    def status(self):
        with self.conn.cursor() as cur:
            cur.execute("SHOW SESSION STATUS WHERE Variable_name IN ('Bytes_sent','Bytes_received') OR Variable_name LIKE 'Handler_read%%'")
            vals = {r["Variable_name"]: int(r["Value"]) for r in cur.fetchall()}
        return {"sent": vals["Bytes_sent"], "recv": vals["Bytes_received"],
                "read": sum(v for k, v in vals.items() if k.startswith("Handler_read"))}


def measure(conn, fn, runs=RUNS, setup=None):
    m = Meter(conn)
    base = [m.status(), m.status()]                  # cost of one status query itself
    cost = {k: base[1][k] - base[0][k] for k in base[0]}
    totals, times = defaultdict(int), []
    for _ in range(runs):
        if setup:
            setup()
        m.trips = m.rows = 0
        before = m.status()
        t0 = time.perf_counter()
        fn(m)
        times.append((time.perf_counter() - t0) * 1000)
        after = m.status()
        for k in before:
            totals[k] += after[k] - before[k] - cost[k]
        totals["trips"] += m.trips
        totals["rows"] += m.rows
    return {"bytes_sent": round(totals["sent"] / runs), "bytes_received": round(totals["recv"] / runs),
            "round_trips": round(totals["trips"] / runs, 1), "rows_read": round(totals["read"] / runs),
            "rows_returned": round(totals["rows"] / runs, 1), "ms": round(statistics.mean(times), 2)}


def main():
    conn = connect()
    probe = Meter(conn)
    customer = probe.run("SELECT CustomerID FROM Orders GROUP BY CustomerID ORDER BY COUNT(*) DESC LIMIT 1")[0]["CustomerID"]
    seller = probe.run("SELECT p.SellerID FROM OrderItem oi JOIN Product p ON p.ProductID = oi.ProductID GROUP BY p.SellerID ORDER BY COUNT(*) DESC LIMIT 1")[0]["SellerID"]
    experiments = []

    # E1 - catalogue page (12 products) --------------------------------------
    def e1_naive(m):
        prods = m.run("SELECT * FROM Product")
        cats = {r["CategoryID"]: r for r in m.run("SELECT * FROM Category")}
        sellers = {r["SellerID"]: r for r in m.run("SELECT * FROM Seller")}
        stock = {r["ProductID"]: r for r in m.run("SELECT * FROM Inventory")}
        reviews = m.run("SELECT * FROM Review")
        rating = defaultdict(list)
        for r in reviews:
            rating[r["ProductID"]].append(r["Rating"])
        page = [p for p in prods if p["Status"] in ("ACTIVE", "OUT_OF_STOCK") and sellers[p["SellerID"]]["Status"] == "ACTIVE"]
        page.sort(key=lambda p: -p["ProductID"])
        return [(p, cats[p["CategoryID"]], stock[p["ProductID"]], rating[p["ProductID"]]) for p in page[:12]]

    def e1_opt(m):
        return m.run("CALL sp_browse_products(NULL, '', '', 12, 0)")
    experiments.append(("E1", "Catalogue page (12 products)", "Read whole tables and filter, join and paginate in the application",
                        "sp_browse_products: selected columns, filtering and LIMIT in the database", e1_naive, e1_opt, None))

    # E2 - customer order history ------------------------------------------------
    def e2_naive(m):
        orders = m.run("SELECT * FROM Orders WHERE CustomerID = %s ORDER BY OrderDate DESC", (customer,))
        for o in orders:                                   # N+1 pattern
            m.run("SELECT * FROM Address WHERE AddressID = %s", (o["AddressID"],))
            items = m.run("SELECT * FROM OrderItem WHERE OrderID = %s", (o["OrderID"],))
            for it in items:
                m.run("SELECT * FROM Product WHERE ProductID = %s", (it["ProductID"],))

    def e2_opt(m):
        return m.run("CALL sp_get_customer_orders(%s)", (customer,))
    experiments.append(("E2", "Order history of a customer", "N+1 queries: one query per order, address and product",
                        "sp_get_customer_orders: one joined and grouped query", e2_naive, e2_opt, None))

    # E3 - seller revenue --------------------------------------------------------
    def e3_naive(m):
        products = {r["ProductID"]: r for r in m.run("SELECT * FROM Product WHERE SellerID = %s", (seller,))}
        orders = {r["OrderID"]: r for r in m.run("SELECT * FROM Orders")}
        items = m.run("SELECT * FROM OrderItem")
        return sum(i["Quantity"] * i["UnitPrice"] for i in items
                   if i["ProductID"] in products and orders[i["OrderID"]]["Status"] != "CANCELLED")

    def e3_opt(m):
        return m.run("CALL sp_seller_dashboard(%s)", (seller,))
    experiments.append(("E3", "Seller dashboard figures", "Download order lines and aggregate in the application",
                        "sp_seller_dashboard: aggregation (SUM, COUNT) in the database", e3_naive, e3_opt, None))

    # E4 - stored order total (controlled redundancy of Part 1) --------------------
    def e4_naive(m):
        return m.run("""SELECT o.OrderID, o.OrderDate, cu.FullName, a.City, SUM(oi.Quantity * oi.UnitPrice) AS TotalAmount, o.Status
                        FROM Orders o JOIN Customer cu ON cu.CustomerID = o.CustomerID JOIN Address a ON a.AddressID = o.AddressID
                        JOIN OrderItem oi ON oi.OrderID = o.OrderID
                        GROUP BY o.OrderID, o.OrderDate, cu.FullName, a.City, o.Status ORDER BY o.OrderDate DESC LIMIT 20""")

    def e4_opt(m):
        return m.run("""SELECT o.OrderID, o.OrderDate, cu.FullName, a.City, o.TotalAmount, o.Status
                        FROM Orders o JOIN Customer cu ON cu.CustomerID = o.CustomerID JOIN Address a ON a.AddressID = o.AddressID
                        ORDER BY o.OrderDate DESC LIMIT 20""")
    experiments.append(("E4", "Order list with totals (20 rows)", "Compute every total from OrderItem (SUM ... GROUP BY)",
                        "Read the stored Orders.TotalAmount (maintained by trg_orderitem_after_insert)", e4_naive, e4_opt, None))

    # E5 - checkout: statement by statement vs one CALL ---------------------------
    address = probe.run("SELECT AddressID FROM Address WHERE CustomerID = %s LIMIT 1", (customer,))[0]["AddressID"]
    products = [r["ProductID"] for r in probe.run(
        "SELECT p.ProductID FROM Product p JOIN Inventory i ON i.ProductID = p.ProductID JOIN Seller s ON s.SellerID = p.SellerID "
        "WHERE p.Status = 'ACTIVE' AND s.Status = 'ACTIVE' AND i.Quantity > 200 LIMIT 2")]

    def fill_cart():
        for pid in products:
            probe.run("CALL sp_cart_add(%s, %s, 1)", (customer, pid))

    def e5_naive(m):
        cart = m.run("SELECT CartID FROM Cart WHERE CustomerID = %s", (customer,))[0]["CartID"]
        m.run("SELECT COUNT(*) AS n FROM CartItem WHERE CartID = %s", (cart,))
        m.run("START TRANSACTION")
        m.run("INSERT INTO Orders (CustomerID, AddressID, OrderDate, TotalAmount, Status) VALUES (%s, %s, NOW(), 0, 'PENDING')", (customer, address))
        oid = m.run("SELECT LAST_INSERT_ID() AS id")[0]["id"]
        m.run("INSERT INTO OrderItem (OrderID, ProductID, Quantity, UnitPrice) SELECT %s, ProductID, Quantity, 0 FROM CartItem WHERE CartID = %s", (oid, cart))
        total = m.run("SELECT TotalAmount FROM Orders WHERE OrderID = %s", (oid,))[0]["TotalAmount"]
        m.run("INSERT INTO Payment (OrderID, Amount, PaymentMethod, Status) VALUES (%s, %s, 'CREDIT_CARD', 'COMPLETED')", (oid, total))
        m.run("UPDATE Orders SET Status = 'PROCESSING' WHERE OrderID = %s", (oid,))
        m.run("DELETE FROM CartItem WHERE CartID = %s", (cart,))
        m.run("COMMIT")

    def e5_opt(m):
        return m.run("CALL sp_place_order(%s, %s, 'CREDIT_CARD')", (customer, address))
    experiments.append(("E5", "Checkout of a 2-line cart", "Application sends each statement of the transaction separately",
                        "sp_place_order: the whole transaction in one CALL", e5_naive, e5_opt, fill_cart))

    results = []
    for code, title, naive_desc, opt_desc, naive, opt, setup in experiments:
        runs = 10 if code == "E5" else RUNS
        n = measure(conn, naive, runs, setup)
        o = measure(conn, opt, runs, setup)
        results.append({"code": code, "title": title, "naive": naive_desc, "optimized": opt_desc, "runs": runs,
                        "naive_metrics": n, "optimized_metrics": o})
        print(f"\n{code} {title}  ({runs} runs)")
        print(f"  {'metric':<16}{'naive':>12}{'procedure':>12}{'change':>10}")
        for k in ["bytes_sent", "bytes_received", "round_trips", "rows_read", "rows_returned", "ms"]:
            change = f"{(o[k] - n[k]) / n[k] * 100:+.0f}%" if n[k] else "-"
            print(f"  {k:<16}{n[k]:>12}{o[k]:>12}{change:>10}")
    out = Path(__file__).with_name("efficiency_results.json")
    out.write_text(json.dumps({"customer": customer, "seller": seller, "results": results}, indent=2, default=str))
    print(f"\nResults written to {out}")


if __name__ == "__main__":
    main()
