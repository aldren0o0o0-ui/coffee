# Alias the canonical AuditLog model defined in app.modules.auth.models
from app.modules.auth.models import AuditLog, AuditActions

__all__ = ["AuditLog", "AuditActions"]
