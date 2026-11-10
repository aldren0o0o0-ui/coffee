"""Test RBAC access controls for Phase 1 & 2 active modules."""


def test_rbac_barista_cannot_access_user_management(client, barista_user):
    """Barista role should NOT have access to user management pages."""
    client.post("/auth/login", data={"username": "test_barista", "password": "Barista123!"}, follow_redirects=True)

    # Barista tries to access user management -> 403 Forbidden
    res = client.get("/users/")
    assert res.status_code == 403

    # Barista tries to create a user -> 403 Forbidden
    res = client.get("/users/create")
    assert res.status_code == 403

    # Barista CAN access dashboard -> 200 OK
    res = client.get("/")
    assert res.status_code == 200

    # Barista CAN access profile -> 200 OK
    res = client.get("/auth/profile")
    assert res.status_code == 200


def test_rbac_staff_cannot_access_user_management(client, staff_user):
    """Staff role should NOT have access to user management pages."""
    client.post("/auth/login", data={"username": "test_staff", "password": "Staff123!"}, follow_redirects=True)

    res = client.get("/users/")
    assert res.status_code == 403

    res = client.get("/users/create")
    assert res.status_code == 403


def test_rbac_cashier_cannot_access_user_management(client, cashier_user):
    """Cashier role should NOT have access to user management pages."""
    client.post("/auth/login", data={"username": "test_cashier", "password": "Cashier123!"}, follow_redirects=True)

    res = client.get("/users/")
    assert res.status_code == 403


def test_rbac_owner_can_access_all(client, owner_user):
    """Owner role should have full access to user management."""
    client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)

    # Owner CAN access user management -> 200 OK
    res = client.get("/users/")
    assert res.status_code == 200

    # Owner CAN access user creation -> 200 OK
    res = client.get("/users/create")
    assert res.status_code == 200

    # Owner CAN access dashboard -> 200 OK
    res = client.get("/")
    assert res.status_code == 200


def test_rbac_manager_can_access_user_management(client, manager_user):
    """Manager role should have access to view user management."""
    client.post("/auth/login", data={"username": "test_manager", "password": "Manager123!"}, follow_redirects=True)

    # Manager CAN access user listing -> 200 OK
    res = client.get("/users/")
    assert res.status_code == 200

    # Manager CAN create users -> 200 OK
    res = client.get("/users/create")
    assert res.status_code == 200


def test_unauthenticated_user_redirected_to_login(client):
    """Unauthenticated users should be redirected to login."""
    res = client.get("/")
    assert res.status_code == 302  # Redirect to login

    res = client.get("/users/")
    assert res.status_code == 302

    res = client.get("/auth/profile")
    assert res.status_code == 302
