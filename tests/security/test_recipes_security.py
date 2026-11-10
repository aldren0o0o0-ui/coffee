def test_unauthenticated_recipes_redirect(client):
    res = client.get("/recipes/")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_cashier_barista_staff_cannot_create_or_modify_recipes(client, cashier_user, barista_user, staff_user, sample_catalog):
    prod = sample_catalog["product"]
    bean = sample_catalog["ingredients"][0]

    for user, pwd in [(cashier_user, "Cashier123!"), (barista_user, "Barista123!"), (staff_user, "Staff123!")]:
        client.post("/auth/login", data={"username": user.username, "password": pwd}, follow_redirects=True)

        # GET create form should be 403
        res = client.get("/recipes/create")
        assert res.status_code == 403

        # POST create should be 403
        res = client.post("/recipes/create", data={
            "product_id": prod.id,
            "ingredient_id[]": [bean.id],
            "quantity_required[]": ["18.0"],
            "unit[]": ["g"]
        })
        assert res.status_code == 403

        # View listing is permitted for barista/staff/cashier
        res = client.get("/recipes/")
        assert res.status_code == 200


def test_manager_and_owner_can_manage_recipes(client, manager_user, owner_user, sample_catalog):
    prod = sample_catalog["product"]
    bean = sample_catalog["ingredients"][0]

    for user, pwd in [(manager_user, "Manager123!"), (owner_user, "Owner123!")]:
        client.post("/auth/login", data={"username": user.username, "password": pwd}, follow_redirects=True)

        # View listing
        res = client.get("/recipes/")
        assert res.status_code == 200

        # View create form
        res = client.get("/recipes/create")
        assert res.status_code == 200

        # Create recipe via form
        res = client.post("/recipes/create", data={
            "product_id": prod.id,
            "ingredient_id[]": [bean.id],
            "quantity_required[]": ["18.0"],
            "unit[]": ["g"],
            "instructions": "Standard espresso extraction"
        }, follow_redirects=True)
        assert res.status_code == 200
        assert b"Standard espresso extraction" in res.data
