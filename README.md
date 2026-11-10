# ☕ Coffee Shop SME Management & POS System

A comprehensive, modular, enterprise-grade Flask application engineered specifically for Small and Medium Enterprises (SMEs) in the specialty coffee and cafe industry.

---

## 🏗️ Architecture & Project Structure

The codebase is engineered strictly following domain-driven modular boundaries:

```
coffee_shop_sme/
│
├── app/
│   ├── __init__.py                # Flask application factory (blueprints, error handlers)
│   ├── extensions.py              # Centralized SQLAlchemy, Migrate, Login, Limiter, CSRF
│   │
│   ├── config/                    # Environment-specific configuration classes
│   │   ├── __init__.py            # BaseConfig & config loader
│   │   ├── development.py         # Dev environment (PostgreSQL / SQLite fallback)
│   │   ├── testing.py             # Isolated in-memory testing configuration
│   │   └── production.py          # Secure cookie & hardened production settings
│   │
│   ├── core/                      # Cross-cutting framework utilities
│   │   ├── __init__.py
│   │   ├── exceptions.py          # App exceptions (NotFoundError, InsufficientStockError, etc.)
│   │   ├── responses.py           # Standard JSON and HTML response helpers
│   │   ├── decorators.py          # @roles_required, @permission_required, @validate_schema
│   │   ├── permissions.py         # Centralized RBAC matrix and role definitions
│   │   ├── validators.py          # Strict data validation (email, SKU, positive numbers)
│   │   ├── pagination.py          # Universal query paginator and PageResult object
│   │   └── utilities.py           # Invoice numbers, currency & date formatting
│   │
│   ├── modules/                   # Domain-Driven Modules
│   │   ├── auth/                  # Authentication, sessions, password reset tokens
│   │   ├── users/                 # User CRUD, role assignments, active status toggle
│   │   ├── dashboard/             # Executive KPI metrics, order volume, live shift summary
│   │   ├── catalog/               # Drink & pastry categories, products, retail beans
│   │   ├── inventory/             # Raw beans, dairy, syrups, packaging, stock movements
│   │   ├── recipes/               # Bill of Materials (BOM), unit economics, auto-deductions
│   │   ├── pos/                   # Touchscreen register, cash float, fast order taking
│   │   ├── sales/                 # Order ledger, receipts, refunds, tax & discount records
│   │   ├── expenses/              # Operating expenses (rent, utilities, equipment maintenance)
│   │   ├── employees/             # Staff directory, hourly wage rates, shift time clock
│   │   ├── reports/               # P&L statement (Revenue - COGS - Opex), CSV export
│   │   ├── audit/                 # Immutable audit logs of administrative actions
│   │   └── settings/              # Store profile, tax rate, receipt headers/footers
│   │
│   ├── templates/                 # Server-Side Rendered Jinja2 Templates
│   │   ├── base.html              # Master layout with Google Outfit typography & tokens
│   │   ├── components/            # Reusable partials (navbar, sidebar, modal, alerts)
│   │   ├── auth/                  # Login and profile views
│   │   ├── dashboard/             # Operational overview
│   │   ├── catalog/               # Menu catalog & category managers
│   │   ├── inventory/             # Stock monitoring, movements, supplier directory
│   │   ├── recipes/               # Recipe builder with live cost breakdown
│   │   ├── pos/                   # Counter POS terminal with responsive cart panel
│   │   ├── sales/                 # Sales history, order details, thermal receipt
│   │   ├── expenses/              # Expense tracking & categories
│   │   ├── employees/             # Staff directory, timesheet kiosk
│   │   ├── reports/               # Profit & Loss financial statements
│   │   ├── audit/                 # System audit logs table
│   │   ├── settings/              # Store branding & preferences
│   │   └── errors/                # 403, 404, 500 custom error pages
│   │
│   └── static/
│       ├── css/                   # Vanilla CSS Design System (Espresso theme)
│       │   ├── variables.css, base.css, layout.css, components.css
│       │   ├── forms.css, tables.css, buttons.css, responsive.css
│       ├── js/                    # Vanilla JS Frontend Modules
│       │   ├── app.js
│       │   ├── utils/             # api.js (CSRF fetch), modal.js, toast.js, form.js
│       │   └── modules/           # pos.js, catalog.js, inventory.js, recipes.js, etc.
│       └── images/                # Brand assets
│
├── migrations/                    # Alembic / Flask-Migrate database migration scripts
├── tests/                         # Pytest test suite
│   ├── conftest.py                # Isolated test fixtures
│   ├── unit/                      # Unit tests for each business domain
│   ├── integration/               # Multi-step user and API workflows
│   └── security/                  # RBAC, CSRF, Password Hashing, Input Validation
├── scripts/
│   ├── seed_database.py           # Seeds full coffee shop menu, recipes, & staff
│   ├── create_owner.py            # CLI tool to bootstrap admin/owner account
│   └── backup_database.py         # JSON snapshot export utility
├── instance/                      # Instance-specific databases & backups
├── .env & .env.example            # Environment variables template
├── .gitignore
├── requirements.txt               # Pinned Python package dependencies
├── run.py                         # Development server launcher
├── wsgi.py                        # Production WSGI application callable
└── README.md
```

---

## ⚡ Quick Start Guide

### 1. Environment Setup & Dependency Installation
Activate the virtual environment and install dependencies:
```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and verify your settings:
```ini
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=change-this-secret-key
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/coffee_db
# Or use SQLite by default if PostgreSQL is not installed locally:
# DATABASE_URL=sqlite:///instance/coffee_dev.db
```

### 3. Seed Realistic Coffee Shop Data
Run the database seed script to populate sample products, raw beans, dairy, recipes (BOM), and staff accounts:
```bash
python scripts/seed_database.py
```

### 4. Run the Development Server
```bash
python run.py
```
Open your browser at `http://localhost:5000`.

---

## 👥 Default Demo Credentials
(All credentials can also be auto-filled with 1 click on the login screen)

| Role | Username / Email | Password | Access Capabilities |
| :--- | :--- | :--- | :--- |
| **Owner** | `owner` (or `owner@coffee.local`) | `OwnerPass123!` (or `OwnerPassword123!`) | Full unrestricted administrative access |
| **Manager** | `manager` (or `manager@coffee.local`) | `ManagerPass123!` | POS, Inventory, Recipes, Staff, Sales, Refunds, Expenses |
| **Cashier** | `cashier` (or `cashier@coffee.local`) | `CashierPass123!` | POS Counter Register, Sales View, Shift Clock-In |
| **Head Barista**| `barista` (or `barista@coffee.local`) | `BaristaPass123!` | POS Counter, Recipes BOM, Shift Clock-In |
| **General Staff**| `staff` (or `staff@coffee.local`) | `StaffPass123!` | Basic Dashboard, Shift Attendance Clock-In |

---

## 🧪 Running the Test Suite

Execute the full suite of unit, integration, and security tests:
```bash
pytest -v tests/
```
To run tests with code coverage:
```bash
pytest --cov=app tests/
```

---

## 🛡️ Security Highlights
- **Role-Based Access Control (RBAC)**: Enforced through `@roles_required` and `@permission_required` decorators across every route.
- **CSRF Protection**: Native Flask-WTF token validation with automatic injection in all forms and asynchronous JS fetch headers.
- **Password Security**: Strong hashing with modern salt algorithms (Scrypt/PBKDF2).
- **Rate Limiting**: Configured with Flask-Limiter to throttle brute-force login attempts.
- **Audit Logging**: Immutable tracking of sensitive events (refunds, role changes, price adjustments).
