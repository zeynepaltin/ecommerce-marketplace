"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Repository classes: each method maps to exactly one stored procedure.
"""
from .database import Database


class Repository:
    def __init__(self, db: Database):
        self.db = db


class AccountRepository(Repository):
    def by_email(self, email):                      return self.db.one("sp_get_user_by_email", email)
    def register_customer(self, email, h, name, phone): return self.db.one("sp_register_customer", email, h, name, phone)
    def register_seller(self, email, h, store):     return self.db.one("sp_register_seller", email, h, store)


class CatalogRepository(Repository):
    def categories(self):                           return self.db.call("sp_list_categories")
    def browse(self, category, search, sort, limit, offset):
        return self.db.call("sp_browse_products", category, search, sort, limit, offset)
    def count(self, category, search):              return self.db.one("sp_count_products", category, search)["Total"]
    def product(self, product_id):                  return self.db.one("sp_get_product_detail", product_id)
    def reviews(self, product_id):                  return self.db.call("sp_get_product_reviews", product_id)


class CustomerRepository(Repository):
    def cart(self, cid):                            return self.db.call("sp_get_cart", cid)
    def cart_count(self, cid):                      return int(self.db.one("sp_get_cart_count", cid)["CartCount"])
    def cart_add(self, cid, pid, qty):              return int(self.db.one("sp_cart_add", cid, pid, qty)["CartCount"])
    def cart_update(self, cid, pid, qty):           return int(self.db.one("sp_cart_update", cid, pid, qty)["CartCount"])
    def addresses(self, cid):                       return self.db.call("sp_list_addresses", cid)
    def add_address(self, cid, city, district, line): return self.db.one("sp_add_address", cid, city, district, line)
    def place_order(self, cid, address_id, method): return self.db.one("sp_place_order", cid, address_id, method)
    def orders(self, cid):                          return self.db.call("sp_get_customer_orders", cid)
    def cancel_order(self, cid, oid):               return self.db.one("sp_cancel_order", cid, oid)
    def reviewable(self, cid):                      return self.db.call("sp_get_reviewable_items", cid)
    def add_review(self, cid, pid, rating, comment): return self.db.one("sp_add_review", cid, pid, rating, comment)


class OrderRepository(Repository):
    """Order detail queries shared by the customer and administrator pages."""
    def header(self, oid, cid=None):                return self.db.one("sp_get_order_header", oid, cid)
    def items(self, oid):                           return self.db.call("sp_get_order_items", oid)
    def payments(self, oid):                        return self.db.call("sp_get_order_payments", oid)
    def shipments(self, oid):                       return self.db.call("sp_get_order_shipments", oid)


class SellerRepository(Repository):
    def dashboard(self, sid):                       return self.db.one("sp_seller_dashboard", sid)
    def top_products(self, sid, limit=5):           return self.db.call("sp_seller_top_products", sid, limit)
    def products(self, sid):                        return self.db.call("sp_seller_products", sid)
    def add_product(self, sid, cat, name, price, qty): return self.db.one("sp_seller_add_product", sid, cat, name, price, qty)
    def update_product(self, sid, pid, name, price, cat, status):
        return self.db.one("sp_seller_update_product", sid, pid, name, price, cat, status)
    def update_stock(self, sid, pid, qty):          return self.db.one("sp_seller_update_stock", sid, pid, qty)
    def pending_items(self, sid):                   return self.db.call("sp_seller_pending_items", sid)
    def create_shipment(self, sid, oid):            return self.db.one("sp_seller_create_shipment", sid, oid)
    def shipments(self, sid):                       return self.db.call("sp_seller_shipments", sid)
    def update_shipment(self, sid, shid, status, tracking):
        return self.db.one("sp_seller_update_shipment", sid, shid, status, tracking)


class AdminRepository(Repository):
    def dashboard(self):                            return self.db.one("sp_admin_dashboard")
    def orders_by_status(self):                     return self.db.call("sp_admin_orders_by_status")
    def top_sellers(self, limit=5):                 return self.db.call("sp_admin_top_sellers", limit)
    def users(self, role, status, q, limit, offset): return self.db.call("sp_admin_list_users", role, status, q, limit, offset)
    def count_users(self, role, status, q):         return self.db.one("sp_admin_count_users", role, status, q)["Total"]
    def set_user_status(self, admin_uid, uid, status): return self.db.one("sp_admin_set_user_status", admin_uid, uid, status)
    def set_seller_status(self, sid, status):       return self.db.one("sp_admin_set_seller_status", sid, status)
    def add_category(self, name, desc):             return self.db.one("sp_admin_add_category", name, desc)
    def update_category(self, cid, name, desc):     return self.db.one("sp_admin_update_category", cid, name, desc)
    def orders(self, status, limit, offset):        return self.db.call("sp_admin_list_orders", status, limit, offset)
    def count_orders(self, status):                 return self.db.one("sp_admin_count_orders", status)["Total"]
    def products(self, q, limit, offset):           return self.db.call("sp_admin_list_products", q, limit, offset)
    def count_products(self, q):                    return self.db.one("sp_admin_count_products", q)["Total"]
    def set_product_status(self, pid, status):      return self.db.one("sp_admin_set_product_status", pid, status)
