def test_login_and_logout_flow(client, owner_user):
    # GET login page
    res = client.get("/auth/login")
    assert res.status_code == 200
    assert b"Sign in to your staff portal" in res.data or b"Internal Management" in res.data

    # POST login
    res = client.post("/auth/login", data={"username": "test_owner", "password": "Owner123!"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Welcome back" in res.data or b"Dashboard" in res.data

    # GET profile
    res = client.get("/auth/profile")
    assert res.status_code == 200
    assert b"My Staff Profile" in res.data

    # POST logout
    res = client.post("/auth/logout", follow_redirects=True)
    assert res.status_code == 200
    assert b"Sign In" in res.data
