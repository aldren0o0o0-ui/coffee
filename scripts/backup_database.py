"""Database backup script to export store data as JSON snapshot."""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.modules.catalog.models import Product, Category
from app.modules.inventory.models import Ingredient, Supplier
from app.modules.sales.models import Sale


def backup():
    app = create_app()
    with app.app_context():
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(__file__), "..", "instance", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.json")

        data = {
            "timestamp": timestamp,
            "categories": [c.to_dict() for c in Category.query.all()],
            "products": [p.to_dict() for p in Product.query.all()],
            "suppliers": [s.to_dict() for s in Supplier.query.all()],
            "ingredients": [i.to_dict() for i in Ingredient.query.all()],
            "sales_count": Sale.query.count()
        }

        with open(backup_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"[OK] Backup created at: {backup_file}")
        return backup_file


if __name__ == "__main__":
    backup()
