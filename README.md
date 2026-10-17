# Multi-Vendor E-Commerce Marketplace

CSE301 Database Management group project.

## Stack
- Backend: Python, FastAPI
- Database: MySQL
- Frontend: To be decided

## Repository layout
- `backend/app/`: FastAPI application and future database integration
- `database/ecommerce_marketplace.sql`: original database creation script (15 tables)
- `frontend/`: frontend placeholder
- `docs/`: E-R diagram, schema and reports

## Getting started
1. Create a virtual environment: `python3 -m venv .venv`
2. Activate it: `source .venv/bin/activate` (macOS/Linux)
3. Install dependencies: `pip install -r backend/requirements.txt`
4. In MySQL Workbench, run `database/ecommerce_marketplace.sql` **once on a fresh database**.
5. Copy `.env.example` to `.env` and update locally when DB integration is implemented.
6. Start the API from the repository root: `uvicorn backend.app.main:app --reload`
7. Open `http://127.0.0.1:8000/docs` for the generated API documentation.

## Current status
- Database creation script included unchanged from the team's supplied SQL.
- Demo INSERT statements, stored procedures, triggers, authentication and frontend are **not implemented yet**.
- `/health` is a minimal FastAPI smoke-test endpoint; it does not test database connectivity.

## Notes
Do not commit `.env`, passwords or production data. The SQL file is not designed to be rerun against an already initialized schema. Cross-table business rules (address ownership, shipment seller/order consistency, role/profile consistency) require additional validation.
