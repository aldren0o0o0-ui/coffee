from app.core.permissions import Permissions, role_has_permission


def can_manage_users(user):
    return user.is_authenticated and (user.is_owner or role_has_permission(user.role, Permissions.MANAGE_USERS))


def can_access_admin_panel(user):
    return user.is_authenticated and user.is_manager_or_above
