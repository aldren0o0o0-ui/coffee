"""Bootstrap script to create or reset the store owner administrator account."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.modules.users.models import User
from app.core.permissions import Roles


def create_owner(username="owner", email="owner@coffee-shop.local", first_name="Store", last_name="Owner", password="OwnerPass123!"):
    app = create_app()
    with app.app_context():
        existing = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing:
            print(f"User '{existing.username}' already exists. Updating credentials and role...")
            existing.role = Roles.OWNER
            existing.first_name = first_name
            existing.last_name = last_name
            existing.is_active = True
            existing.set_password(password)
            db.session.commit()
            print(f"Owner account updated successfully: {existing.username} / {email}")
            return existing

        owner = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=Roles.OWNER,
            is_active=True
        )
        owner.set_password(password)
        db.session.add(owner)
        db.session.commit()
        print(f"Owner account created successfully!")
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print(f"  Role:     {Roles.OWNER}")
        return owner


if __name__ == "__main__":
    u = sys.argv[1] if len(sys.argv) > 1 else "owner"
    p = sys.argv[2] if len(sys.argv) > 2 else "OwnerPass123!"
    create_owner(username=u, password=p)
