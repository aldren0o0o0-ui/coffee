from datetime import datetime
from app.extensions import db
from app.modules.users.models import User
from app.modules.auth.models import AuditLog, AuditActions
from app.core.permissions import Roles
from app.core.exceptions import NotFoundError, ValidationError, ConflictError, ForbiddenError
from app.core.pagination import paginate_query
from app.core.validators import validate_email_format


class UserService:
    @staticmethod
    def get_users_paginated(page=1, per_page=15, role=None, is_active=None, search=None):
        query = User.query
        if role and role.upper() in Roles.ALL:
            query = query.filter_by(role=role.upper())
        if is_active is not None and is_active != "":
            active_bool = str(is_active).lower() in ("1", "true", "yes")
            query = query.filter_by(is_active=active_bool)
        if search and search.strip():
            s = f"%{search.strip()}%"
            query = query.filter(
                (User.username.ilike(s)) |
                (User.first_name.ilike(s)) |
                (User.last_name.ilike(s)) |
                (User.email.ilike(s))
            )
        query = query.order_by(User.created_at.desc())
        return paginate_query(query, page=page, per_page=per_page)

    @staticmethod
    def get_user_by_id(user_id):
        user = db.session.get(User, user_id)
        if not user:
            raise NotFoundError("User record not found.")
        return user

    @staticmethod
    def create_user(username, email, first_name, last_name, password, role, is_active=True, actor=None, ip_address=None):
        # 1. Validation
        if not username or len(username.strip()) < 3:
            raise ValidationError("Username must be at least 3 characters.")
        clean_username = username.strip()

        validate_email_format(email)
        clean_email = email.strip().lower()

        if not first_name or not first_name.strip():
            raise ValidationError("First name is required.")
        if not last_name or not last_name.strip():
            raise ValidationError("Last name is required.")

        clean_role = role.upper() if role else Roles.STAFF
        if clean_role not in Roles.ALL:
            raise ValidationError(f"Invalid role. Must be one of: {', '.join(Roles.ALL)}")

        # Privilege escalation check: only OWNER can create another OWNER
        if clean_role == Roles.OWNER and actor and not actor.is_owner:
            raise ForbiddenError("Only an existing Store Owner can grant the OWNER role.")

        if not password or len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")

        # Duplicate checks
        if User.query.filter_by(username=clean_username).first():
            raise ConflictError(f"Username '{clean_username}' is already registered.")
        if User.query.filter_by(email=clean_email).first():
            raise ConflictError(f"Email '{clean_email}' is already registered.")

        # 2. Creation
        user = User(
            username=clean_username,
            email=clean_email,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            role=clean_role,
            is_active=bool(is_active)
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Audit
        AuditLog.log(
            action=AuditActions.USER_CREATED,
            user_id=actor.id if actor else None,
            username=actor.username if actor else "System",
            ip_address=ip_address,
            details=f"Created user '{user.username}' with role '{user.role}'"
        )
        return user

    @staticmethod
    def update_user(user_id, first_name=None, last_name=None, email=None, role=None, is_active=None, password=None, actor=None, ip_address=None):
        user = UserService.get_user_by_id(user_id)

        # Protection: MANAGER cannot edit an OWNER account
        if user.is_owner and actor and not actor.is_owner:
            raise ForbiddenError("Managers cannot modify Store Owner accounts.")

        role_changed = False
        old_role = user.role

        if role:
            clean_role = role.upper()
            if clean_role not in Roles.ALL:
                raise ValidationError(f"Invalid role: {clean_role}")
            if clean_role == Roles.OWNER and actor and not actor.is_owner:
                raise ForbiddenError("Only a Store Owner can assign the OWNER role.")
            if clean_role != user.role:
                user.role = clean_role
                role_changed = True

        if email:
            validate_email_format(email)
            clean_email = email.strip().lower()
            if clean_email != user.email:
                existing = User.query.filter(User.email == clean_email, User.id != user.id).first()
                if existing:
                    raise ConflictError(f"Email '{clean_email}' is already registered.")
                user.email = clean_email

        if first_name and first_name.strip():
            user.first_name = first_name.strip()

        if last_name and last_name.strip():
            user.last_name = last_name.strip()

        if is_active is not None:
            # Prevent deactivating yourself
            if actor and actor.id == user.id and not bool(is_active):
                raise ValidationError("You cannot deactivate your own logged-in account.")
            user.is_active = bool(is_active)

        if password and password.strip():
            if len(password.strip()) < 8:
                raise ValidationError("New password must be at least 8 characters long.")
            user.set_password(password.strip())

        db.session.commit()

        # Audit
        if role_changed:
            AuditLog.log(
                action=AuditActions.ROLE_CHANGED,
                user_id=actor.id if actor else None,
                username=actor.username if actor else "System",
                ip_address=ip_address,
                details=f"Changed user '{user.username}' role from {old_role} to {user.role}"
            )
        else:
            AuditLog.log(
                action=AuditActions.USER_UPDATED,
                user_id=actor.id if actor else None,
                username=actor.username if actor else "System",
                ip_address=ip_address,
                details=f"Updated details for user '{user.username}'"
            )

        return user

    @staticmethod
    def toggle_user_status(user_id, actor=None, ip_address=None):
        user = UserService.get_user_by_id(user_id)

        if actor and actor.id == user.id:
            raise ValidationError("You cannot deactivate your own account.")

        if user.is_owner and not (actor and actor.is_owner):
            raise ForbiddenError("Only a Store Owner can modify an Owner's status.")

        user.is_active = not user.is_active
        db.session.commit()

        action = AuditActions.ACCOUNT_ACTIVATED if user.is_active else AuditActions.ACCOUNT_DEACTIVATED
        AuditLog.log(
            action=action,
            user_id=actor.id if actor else None,
            username=actor.username if actor else "System",
            ip_address=ip_address,
            details=f"Account '{user.username}' {'activated' if user.is_active else 'deactivated'}"
        )
        return user
