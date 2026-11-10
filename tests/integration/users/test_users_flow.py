"""Integration tests for User Management flows (Phase 1 & 2)."""


def test_user_listing_page(client, owner_user):
    """Owner should see the user listing with search and filters."""
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)

    res = client.get("/users/")
    assert res.status_code == 200
    assert b"Staff Accounts" in res.data
    assert b"test_owner" in res.data


def test_user_create_flow(client, owner_user):
    """Owner can create a new staff account via the web form."""
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)

    # GET create form
    res = client.get("/users/create")
    assert res.status_code == 200
    assert b"Create Staff Account" in res.data

    # POST create form
    res = client.post("/users/create", data={
        "username": "new_barista",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@coffee.local",
        "password": "JanePass123!",
        "role": "BARISTA",
        "is_active": "1"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"new_barista" in res.data
    assert b"created successfully" in res.data


def test_user_edit_flow(client, owner_user, barista_user):
    """Owner can edit a staff account."""
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)

    # GET edit form
    res = client.get(f"/users/{barista_user.id}/edit")
    assert res.status_code == 200
    assert b"Edit Account" in res.data

    # POST edit form
    res = client.post(f"/users/{barista_user.id}/edit", data={
        "first_name": "Updated",
        "last_name": "Barista",
        "email": "updated_barista@test.local",
        "role": "BARISTA",
        "is_active": "1"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"updated successfully" in res.data


def test_user_toggle_status_flow(client, owner_user, barista_user):
    """Owner can deactivate and reactivate a staff account."""
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)

    # Toggle status (deactivate)
    res = client.post(f"/users/{barista_user.id}/toggle-status", follow_redirects=True)
    assert res.status_code == 200
    assert b"deactivated" in res.data

    # Toggle status (reactivate)
    res = client.post(f"/users/{barista_user.id}/toggle-status", follow_redirects=True)
    assert res.status_code == 200
    assert b"activated" in res.data


def test_inactive_user_cannot_login(client, owner_user, barista_user):
    """Deactivated accounts should not be able to authenticate."""
    # Owner deactivates barista
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)
    client.post(f"/users/{barista_user.id}/toggle-status", follow_redirects=True)
    client.post("/auth/logout", follow_redirects=True)

    # Barista tries to login -> should fail
    res = client.post("/auth/login", data={"username": "test_barista", "password": "Barista123!"}, follow_redirects=True)
    assert b"Invalid" in res.data or b"deactivated" in res.data or b"danger" in res.data
