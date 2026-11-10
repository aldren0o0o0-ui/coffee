def test_pos_flow(client, barista_user, sample_catalog):
    client.post("/auth/login", data={"username": "test_barista", "password": "Barista123!"}, follow_redirects=True)

    # Open shift
    res = client.post("/pos/shift/open", data={"opening_cash": "150.00"}, follow_redirects=True)
    assert res.status_code == 200

    # Render POS page
    res = client.get("/pos/")
    assert res.status_code == 200
    assert b"POS Counter Terminal" in res.data
    assert b"Latte" in res.data
