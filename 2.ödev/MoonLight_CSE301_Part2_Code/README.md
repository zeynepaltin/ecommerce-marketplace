# Multi-Vendor E-Commerce Marketplace

CSE 301 Database Management, Fall 2026 – Group **Moon Light**

| Name Surname | Student Number |
|---|---|
| Mehmet Çolaker | 220610028 |
| Emre Sefa Kazan | 230610019 |
| Ahmet Yasin Akyüz | 230610015 |
| Hüseyin Gürses | 230610029 |
| Zeynep Sümeyra Altın | 230610005 |
| Ulaş Budak | 25060902060 |

A multi-page web marketplace where many independent stores sell through one site. A customer order can contain
products from several stores, and every store ships its own part separately. Three roles: **Customer**, **Seller**, **Admin**.

## Technology
Python 3.10+ · FastAPI · Jinja2 · Bootstrap 5 (bundled, works offline) · PyMySQL · MySQL 8.0 (InnoDB)

The application accesses the database **only through stored procedures** (47 procedures, 11 triggers).

## Setup
1. **Database** – in MySQL Workbench (or the `mysql` client) run, in this order:
   1. `database/MoonLight_CSE301_Part1_DB.sql` – schema and sample data (drops and re-creates `ecommerce_marketplace`)
   2. `database/MoonLight_CSE301_Part2_Procedures_Triggers.sql` – stored procedures and triggers

   Re-running both files restores the initial data at any time (recommended before the video demo).
2. **Python packages** (from the repository root):
   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
   pip install -r backend/requirements.txt
   ```
3. **Configuration** – copy `.env.example` to `.env` and enter your MySQL user name and password.
4. **Start** (from the repository root):
   ```
   uvicorn backend.app.main:app --reload
   ```
   Open http://127.0.0.1:8000

## Demo accounts (password for all: `Demo1234!`)
| Role | E-mail |
|---|---|
| Admin | admin01@moonlightmarket.com |
| Seller | info@cinarelektronik.com.tr |
| Seller (pending approval) | info@kuzeyotoaksesuar.com.tr |
| Customer | seda.korkmaz@hotmail.com |

Every customer and seller in the sample data can sign in with the same password (e-mail addresses are in the `Users` table).

## Tests and efficiency study
Run on a freshly initialised database (step 1), from the repository root:
```
python tests/test_database.py     # 71 checks: every stored procedure and trigger
python tests/test_web.py          # 71 checks: complete workflows of all roles through the web application
python tools/efficiency_study.py  # data-traffic measurements used in Section 7 of the report
```
These programs change data (orders, accounts); re-run the two SQL files afterwards.

## Repository layout
```
backend/app/main.py            application, middleware, error pages
backend/app/config.py          settings from .env
backend/app/database.py        Database class: CALL sp_...(...) in one round trip
backend/app/repositories.py    repository classes, one method per stored procedure
backend/app/session.py         sessions, idle timeout, activity tracker, role checks
backend/app/security.py        bcrypt password hashing
backend/app/web.py             template helpers, pagination
backend/app/routers/           public, auth, customer, seller, admin pages
backend/app/templates/         24 Jinja2 templates
backend/app/static/            CSS and bundled Bootstrap 5.3.3 / Bootstrap Icons 1.11.3 (MIT licence)
database/                      Part 1 and Part 2 SQL files
tests/                         automated tests
tools/                         efficiency study and its last results
docs/DEMO_SCRIPT.md            plan for the video demonstration
```
