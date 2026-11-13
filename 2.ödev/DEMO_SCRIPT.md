# Video Demonstration Plan – Moon Light (CSE 301, Part 2)

Target length: **about 10 minutes**. The specification allows only a short window after the Part 2 deadline, so
rehearse once beforehand and record in one session. Every member presents one part (adjust the names if needed).

## Before recording (5 minutes)
1. Re-run `database/MoonLight_CSE301_Part1_DB.sql` and then `database/MoonLight_CSE301_Part2_Procedures_Triggers.sql`.
2. Start the server: `uvicorn backend.app.main:app` and open http://127.0.0.1:8000.
3. Prepare three browser windows (or one normal + two private windows) so that a customer, a seller and the admin
   can be signed in at the same time. Use 110–125 % zoom so the text is readable in the recording.
4. Keep MySQL Workbench open with the Part 2 SQL file for the database part.

## Script

| Time | Presenter | What to show | What to say (key points) |
|---|---|---|---|
| 0:00–0:45 | Mehmet Çolaker | Title slide or the home page | Group, project idea: many stores, one cart, one shipment per store. Stack: FastAPI, MySQL, 47 stored procedures, 11 triggers. |
| 0:45–2:15 | Emre Sefa Kazan | Visitor: home page, catalogue (category, search, sort, page 2), product page. Register a new customer, sign in. | Pagination and filtering happen in `sp_browse_products`; the page receives only 12 rows. Registration calls `sp_register_customer`. |
| 2:15–4:15 | Ahmet Yasin Akyüz | Customer: add **two products of different stores** to the cart (badge changes), change a quantity, try a quantity above the stock (error message), add an address, check out. Order page shows PROCESSING and "not shipped yet". | Cart count is a session variable. `sp_place_order` is one transaction; the OrderItem triggers check stock, set the price, reduce stock and compute the total. |
| 4:15–6:00 | Hüseyin Gürses | Seller window: sign in as the seller of the first product → dashboard → *Orders to ship* (only own items) → *Create shipment* → try *Mark shipped* without tracking number (error) → enter tracking number → *Mark delivered*. Switch to the customer: order still PROCESSING. Sign in as the second seller and complete the second shipment. Customer: order now DELIVERED. | Seller-specific fulfilment. `trg_shipmentitem_before_insert` blocks foreign items, `trg_shipment_after_update` derives the order status from all shipments. |
| 6:00–7:15 | Zeynep Sümeyra Altın | Customer: *Reviews* → review a delivered product → product page shows it. Place a second order and cancel it (refund). *My session* page: session variables and page history. | `trg_review_before_insert` accepts only delivered products; `trg_orders_after_update` returns stock on cancellation. Idle timeout of 30 minutes. |
| 7:15–8:45 | Ulaş Budak | Admin: dashboard (figures, orders by status, **users online with current page**), *Users & stores*: filter pending stores and approve one; suspend a store → its products disappear from the catalogue; product moderation; add a category; open an order. Try opening `/admin` as the customer (403). | Activity tracking; `trg_seller_after_update`; role-based access control with `require_role()`. |
| 8:45–10:00 | Mehmet Çolaker | MySQL Workbench: show one JOIN procedure (e.g. `sp_seller_pending_items`) and one trigger; show the efficiency table (report Table 10) and run `python tests/test_database.py` (71/71). Sign out. | 19 procedures join 3–6 tables; efficiency study: up to 99 % less data and 96 % fewer round trips; logout clears the session. |

## Useful accounts (password `Demo1234!`)
- Admin: `admin01@moonlightmarket.com`
- Store waiting for approval: `info@kuzeyotoaksesuar.com.tr`
- Customer with history: `seda.korkmaz@hotmail.com`
- The seller of a product: shown on the product page ("Sold and shipped by …"); find its e-mail on *Users & stores* by searching the store name.

## Checklist after recording
- The video shows the code version that was submitted (no changes after the deadline).
- All three roles, login/logout, a multi-store order, a trigger error message and the efficiency results are visible.
- Export in a common format (MP4), check the sound, and upload within the announced window.
