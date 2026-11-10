"""Role-Based Access Control (RBAC) definitions and permission hierarchies for Coffee Shop SME."""

class Roles:
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    CASHIER = "CASHIER"
    BARISTA = "BARISTA"
    STAFF = "STAFF"

    ALL = [OWNER, MANAGER, CASHIER, BARISTA, STAFF]


class Permissions:
    # Dashboard & General
    DASHBOARD_VIEW = "dashboard.view"

    # User Management
    USERS_VIEW = "users.view"
    USERS_CREATE = "users.create"
    USERS_UPDATE = "users.update"
    USERS_DEACTIVATE = "users.deactivate"

    # Settings
    SETTINGS_MANAGE = "settings.manage"

    # Menu Catalog (Phase 3)
    CATALOG_VIEW = "catalog.view"
    CATALOG_CREATE = "catalog.create"
    CATALOG_UPDATE = "catalog.update"
    CATALOG_DEACTIVATE = "catalog.deactivate"
    CATALOG_MANAGE = "catalog.manage"

    # Raw Material Inventory (Phase 4)
    INVENTORY_VIEW = "inventory.view"
    INVENTORY_CREATE = "inventory.create"
    INVENTORY_UPDATE = "inventory.update"
    INVENTORY_ADJUST = "inventory.adjust"
    INVENTORY_RECEIVE = "inventory.receive"
    INVENTORY_VIEW_MOVEMENTS = "inventory.view_movements"
    INVENTORY_MANAGE_SUPPLIERS = "inventory.manage_suppliers"
    INVENTORY_MANAGE = "inventory.manage"

    # Drink Recipes & BOM (Phase 5)
    RECIPES_VIEW = "recipes.view"
    RECIPES_CREATE = "recipes.create"
    RECIPES_EDIT = "recipes.edit"
    RECIPES_DELETE = "recipes.delete"
    RECIPES_MANAGE = "recipes.manage"

    # POS Counter & Register (Phase 6)
    POS_VIEW = "pos.view"
    POS_CHECKOUT = "pos.checkout"
    POS_OPEN_SHIFT = "pos.open_shift"
    POS_CLOSE_SHIFT = "pos.close_shift"
    POS_REFUND = "pos.refund"
    POS_MANAGE = "pos.manage"

    # Sales Orders & Ledger (Phase 7)
    SALES_VIEW = "sales.view"
    SALES_REFUND = "sales.refund"
    SALES_VOID = "sales.void"
    SALES_EXPORT = "sales.export"
    SALES_MANAGE = "sales.manage"

    # Operating Expenses (Phase 8)
    EXPENSES_VIEW = "expenses.view"
    EXPENSES_CREATE = "expenses.create"
    EXPENSES_EDIT = "expenses.edit"
    EXPENSES_VOID = "expenses.void"
    EXPENSES_MANAGE = "expenses.manage"

    # Staff & Attendance (Phase 9)
    EMPLOYEES_VIEW = "employees.view"
    EMPLOYEES_MANAGE = "employees.manage"
    SCHEDULES_VIEW = "schedules.view"
    SCHEDULES_MANAGE = "schedules.manage"
    ATTENDANCE_VIEW = "attendance.view"
    ATTENDANCE_MANAGE = "attendance.manage"
    ATTENDANCE_CORRECT = "attendance.correct"
    ATTENDANCE_SELF_VIEW = "attendance.self_view"
    ATTENDANCE_SELF_CLOCK = "attendance.self_clock"

    # Reporting & Analytics (Phase 10)
    REPORTS_VIEW = "reports.view"
    REPORTS_FINANCIAL = "reports.financial"
    REPORTS_OPERATIONAL = "reports.operational"
    REPORTS_EXPORT = "reports.export"


# Map roles to their permitted capabilities
ROLE_PERMISSIONS = {
    Roles.OWNER: {
        Permissions.DASHBOARD_VIEW,
        Permissions.USERS_VIEW,
        Permissions.USERS_CREATE,
        Permissions.USERS_UPDATE,
        Permissions.USERS_DEACTIVATE,
        Permissions.SETTINGS_MANAGE,
        # Catalog
        Permissions.CATALOG_VIEW,
        Permissions.CATALOG_CREATE,
        Permissions.CATALOG_UPDATE,
        Permissions.CATALOG_DEACTIVATE,
        Permissions.CATALOG_MANAGE,
        # Inventory
        Permissions.INVENTORY_VIEW,
        Permissions.INVENTORY_CREATE,
        Permissions.INVENTORY_UPDATE,
        Permissions.INVENTORY_ADJUST,
        Permissions.INVENTORY_RECEIVE,
        Permissions.INVENTORY_VIEW_MOVEMENTS,
        Permissions.INVENTORY_MANAGE_SUPPLIERS,
        Permissions.INVENTORY_MANAGE,
        # Recipes
        Permissions.RECIPES_VIEW,
        Permissions.RECIPES_CREATE,
        Permissions.RECIPES_EDIT,
        Permissions.RECIPES_DELETE,
        Permissions.RECIPES_MANAGE,
        # POS
        Permissions.POS_VIEW,
        Permissions.POS_CHECKOUT,
        Permissions.POS_OPEN_SHIFT,
        Permissions.POS_CLOSE_SHIFT,
        Permissions.POS_REFUND,
        Permissions.POS_MANAGE,
        # Sales Ledger (Phase 7)
        Permissions.SALES_VIEW,
        Permissions.SALES_REFUND,
        Permissions.SALES_VOID,
        Permissions.SALES_EXPORT,
        Permissions.SALES_MANAGE,
        # Operating Expenses (Phase 8)
        Permissions.EXPENSES_VIEW,
        Permissions.EXPENSES_CREATE,
        Permissions.EXPENSES_EDIT,
        Permissions.EXPENSES_VOID,
        Permissions.EXPENSES_MANAGE,
        # Staff & Attendance (Phase 9)
        Permissions.EMPLOYEES_VIEW,
        Permissions.EMPLOYEES_MANAGE,
        Permissions.SCHEDULES_VIEW,
        Permissions.SCHEDULES_MANAGE,
        Permissions.ATTENDANCE_VIEW,
        Permissions.ATTENDANCE_MANAGE,
        Permissions.ATTENDANCE_CORRECT,
        Permissions.ATTENDANCE_SELF_VIEW,
        Permissions.ATTENDANCE_SELF_CLOCK,
        # Reporting (Phase 10)
        Permissions.REPORTS_VIEW,
        Permissions.REPORTS_FINANCIAL,
        Permissions.REPORTS_OPERATIONAL,
        Permissions.REPORTS_EXPORT,
    },
    Roles.MANAGER: {
        Permissions.DASHBOARD_VIEW,
        Permissions.USERS_VIEW,
        Permissions.USERS_CREATE,
        Permissions.USERS_UPDATE,
        Permissions.USERS_DEACTIVATE,
        # Catalog
        Permissions.CATALOG_VIEW,
        Permissions.CATALOG_CREATE,
        Permissions.CATALOG_UPDATE,
        Permissions.CATALOG_DEACTIVATE,
        Permissions.CATALOG_MANAGE,
        # Inventory
        Permissions.INVENTORY_VIEW,
        Permissions.INVENTORY_CREATE,
        Permissions.INVENTORY_UPDATE,
        Permissions.INVENTORY_ADJUST,
        Permissions.INVENTORY_RECEIVE,
        Permissions.INVENTORY_VIEW_MOVEMENTS,
        Permissions.INVENTORY_MANAGE_SUPPLIERS,
        Permissions.INVENTORY_MANAGE,
        # Recipes
        Permissions.RECIPES_VIEW,
        Permissions.RECIPES_CREATE,
        Permissions.RECIPES_EDIT,
        Permissions.RECIPES_DELETE,
        Permissions.RECIPES_MANAGE,
        # POS
        Permissions.POS_VIEW,
        Permissions.POS_CHECKOUT,
        Permissions.POS_OPEN_SHIFT,
        Permissions.POS_CLOSE_SHIFT,
        Permissions.POS_REFUND,
        Permissions.POS_MANAGE,
        # Sales Ledger (Phase 7)
        Permissions.SALES_VIEW,
        Permissions.SALES_REFUND,
        Permissions.SALES_VOID,
        Permissions.SALES_EXPORT,
        Permissions.SALES_MANAGE,
        # Operating Expenses (Phase 8)
        Permissions.EXPENSES_VIEW,
        Permissions.EXPENSES_CREATE,
        Permissions.EXPENSES_EDIT,
        Permissions.EXPENSES_VOID,
        Permissions.EXPENSES_MANAGE,
        # Staff & Attendance (Phase 9)
        Permissions.EMPLOYEES_VIEW,
        Permissions.EMPLOYEES_MANAGE,
        Permissions.SCHEDULES_VIEW,
        Permissions.SCHEDULES_MANAGE,
        Permissions.ATTENDANCE_VIEW,
        Permissions.ATTENDANCE_MANAGE,
        Permissions.ATTENDANCE_CORRECT,
        Permissions.ATTENDANCE_SELF_VIEW,
        Permissions.ATTENDANCE_SELF_CLOCK,
        # Reporting (Phase 10)
        Permissions.REPORTS_VIEW,
        Permissions.REPORTS_FINANCIAL,
        Permissions.REPORTS_OPERATIONAL,
        Permissions.REPORTS_EXPORT,
    },
    Roles.CASHIER: {
        Permissions.DASHBOARD_VIEW,
        Permissions.CATALOG_VIEW,
        Permissions.INVENTORY_VIEW,
        Permissions.INVENTORY_VIEW_MOVEMENTS,
        Permissions.RECIPES_VIEW,
        Permissions.POS_VIEW,
        Permissions.POS_CHECKOUT,
        Permissions.POS_OPEN_SHIFT,
        Permissions.POS_CLOSE_SHIFT,
        Permissions.SALES_VIEW,
        Permissions.SALES_EXPORT,
        # Staff & Attendance (Phase 9)
        Permissions.SCHEDULES_VIEW,
        Permissions.ATTENDANCE_SELF_VIEW,
        Permissions.ATTENDANCE_SELF_CLOCK,
        # Reporting (Phase 10)
        Permissions.REPORTS_VIEW,
        Permissions.REPORTS_OPERATIONAL,
    },
    Roles.BARISTA: {
        Permissions.DASHBOARD_VIEW,
        Permissions.CATALOG_VIEW,
        Permissions.INVENTORY_VIEW,
        Permissions.INVENTORY_VIEW_MOVEMENTS,
        Permissions.RECIPES_VIEW,
        Permissions.POS_VIEW,
        # Staff & Attendance (Phase 9)
        Permissions.SCHEDULES_VIEW,
        Permissions.ATTENDANCE_SELF_VIEW,
        Permissions.ATTENDANCE_SELF_CLOCK,
    },
    Roles.STAFF: {
        Permissions.DASHBOARD_VIEW,
        Permissions.CATALOG_VIEW,
        Permissions.INVENTORY_VIEW,
        Permissions.RECIPES_VIEW,
        Permissions.SALES_VIEW,
        # Staff & Attendance (Phase 9)
        Permissions.SCHEDULES_VIEW,
        Permissions.ATTENDANCE_SELF_VIEW,
        Permissions.ATTENDANCE_SELF_CLOCK,
    },
}


def role_has_permission(role: str, permission: str) -> bool:
    """Check if a specific role contains a given permission."""
    if not role:
        return False
    return permission in ROLE_PERMISSIONS.get(role.upper(), set())
