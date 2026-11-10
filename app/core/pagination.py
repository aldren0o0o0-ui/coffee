from flask import request


class PageResult:
    def __init__(self, items, total, page, per_page):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page
        self.pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1 if self.has_prev else None
        self.next_num = page + 1 if self.has_next else None

    def to_dict(self, item_serializer=None):
        return {
            "items": [item_serializer(item) if item_serializer else (item.to_dict() if hasattr(item, "to_dict") else item) for item in self.items],
            "total": self.total,
            "page": self.page,
            "per_page": self.per_page,
            "pages": self.pages,
            "has_prev": self.has_prev,
            "has_next": self.has_next,
        }


def paginate_query(query, page=None, per_page=15, default_page=1):
    """Paginate a SQLAlchemy query object with safe defaults."""
    if page is None:
        try:
            page = int(request.args.get("page", default_page))
        except (ValueError, TypeError):
            page = default_page

    try:
        req_per_page = int(request.args.get("per_page", per_page))
        per_page = min(max(req_per_page, 1), 100)
    except (ValueError, TypeError):
        pass

    page = max(page, 1)
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return PageResult(items=items, total=total, page=page, per_page=per_page)
