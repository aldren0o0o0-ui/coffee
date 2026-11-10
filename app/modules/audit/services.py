from app.extensions import db
from app.modules.audit.models import AuditLog
from app.core.pagination import paginate_query


class AuditService:
    @staticmethod
    def log(action, entity_type, entity_id=None, details="", user_id=None, ip_address=None):
        log_entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            details=details,
            user_id=user_id,
            ip_address=ip_address
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry

    @staticmethod
    def get_logs_paginated(page=1, per_page=20, action=None, entity_type=None):
        query = AuditLog.query
        if action:
            query = query.filter_by(action=action)
        if entity_type:
            query = query.filter_by(entity_type=entity_type)
        query = query.order_by(AuditLog.timestamp.desc())
        return paginate_query(query, page=page, per_page=per_page)
