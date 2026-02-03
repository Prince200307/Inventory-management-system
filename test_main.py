import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

import database
from main import app

TEST_DB_FOLDER= "test_database"
TEST_DB_PATH = os.path.join(TEST_DB_FOLDER, "mock_inventory.db")

def setup_test_db():
    if not os.path.exists(TEST_DB_FOLDER):
        os.makedirs(TEST_DB_FOLDER)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    database.DB_PATH = TEST_DB_PATH
    database.setup_database()

def teardown_test_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    if os.path.exists(TEST_DB_FOLDER):
        os.rmdir(TEST_DB_FOLDER)

@pytest.fixture(scope="module")
def client():
    setup_test_db()
    client = TestClient(app)
    yield client
    teardown_test_db()

#--------------------------------------root and health check--------------------------------------#
def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Inventory Management API is running." in response.json()["message"]

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data

#--------------------------------------test create functions--------------------------------------#
def test_create_product_success(client):
    response = client.post("/products", json={
        "product_name": "laptop",
        "quantity": 10,
    })
    assert response.status_code == 201
    data = response.json()

    assert data['product']["success"] is True
    assert data["product"]["product"]["product_name"] == "laptop"
    assert data["product"]["product"]["quantity"] == 10

def test_create_product_missing_fields(client):
    response = client.post("/products", json={
        "product_name": "laptop"
    })
    assert response.status_code == 422

def test_create_product_empty_name_fails(client):
    response = client.post("/products", json={
        "product_name": "",
        "quantity": 5
    })
    assert response.status_code == 422

def test_create_product_invalid_name_fails(client):
    response = client.post("/products", json={
        "product_name": "Laptop@123",
        "quantity": 5
    })
    assert response.status_code == 422

def test_create_product_negative_quantity(client):
    response = client.post("/products", json={
        "product_name": "laptop",
        "quantity": -5
    })
    assert response.status_code == 422
    data = response.json()
    assert data["detail"][0]["msg"] == "Input should be greater than or equal to 0"

def test_create_product_duplicate_name(client):
    client.post("/products", json={
        "product_name": "Phone",
        "quantity": 15
    })
    response = client.post("/products", json={
        "product_name": "Phone",
        "quantity": 5
    })
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "Product 'Phone' already exists"

def test_create_product_name_too_long_fails(client):
    long_name = "A" * 101
    response = client.post("/products", json={
        "product_name": long_name,
        "quantity": 10
    })
    assert response.status_code == 422

def test_create_product_name_only_spaces_fails(client):
    response = client.post("/products", json={
        "product_name": "     ",
        "quantity": 10
    })
    assert response.status_code == 422

def test_zero_quantity_product_creation(client):
    response = client.post("/products", json={
        "product_name": "Iphone Charger",
        "quantity": 0
    })
    assert response.status_code == 201
    data = response.json()
    assert data['product']["success"] is True
    assert data["product"]["product"]["product_name"] == "Iphone Charger"
    assert data["product"]["product"]["quantity"] == 0

#--------------------------------------test get products--------------------------------------#

def test_get_all_products(client):
    client.post("/products", json={
        "product_name": "Keyboard",
        "quantity": 20
    })
    client.post("/products", json={
        "product_name": "Mouse",
        "quantity": 11
    })
    response = client.get("/products/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2  # At least two or more products should exist

def test_get_product_by_id_success(client):
    post_response = client.post("/products", json={
        "product_name": "Massager",
        "quantity": 7
    })
    product_id = post_response.json()["product"]["product"]["id"]

    get_response = client.get(f"/products/{product_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["product_name"] == "Massager"
    assert data["quantity"] == 7

def test_get_product_by_id_not_found(client):
    response = client.get("/products/9999")
    assert response.status_code == 404

#--------------------------------------test update product--------------------------------------#

def test_update_product_quantity_success(client):
    post_response = client.post("/products", json={
        "product_name": "Tablet",
        "quantity": 12
    })
    product_id = post_response.json()["product"]["product"]["id"]

    update_response = client.put(f"/products/{product_id}/quantity", json={
        "quantity": 15
    })
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["product"]["product"]["product_name"] == "Tablet"
    assert data["product"]["product"]["quantity"] == 15

def test_update_product_quantity_negative_fails(client):
    post_response = client.post("/products", json={
        "product_name": "TV",
        "quantity": 8
    })
    product_id = post_response.json()["product"]["product"]["id"]

    update_response = client.put(f"/products/{product_id}/quantity", json={
        "quantity": -3
    })
    assert update_response.status_code == 422

def test_update_product_quantity_not_found(client):
    response = client.put("/products/9999/quantity", json={
        "quantity": 10
    })
    assert response.status_code == 400

#--------------------------------------test add quantity--------------------------------------#

def test_add_product_quantity_success(client):
    post_response = client.post("/products", json={
        "product_name": "Camera",
        "quantity": 5
    })
    product_id = post_response.json()["product"]["product"]["id"]

    add_response = client.post(f"/products/{product_id}/add", json={
        "adjustment": 10
    })
    assert add_response.status_code == 200
    data = add_response.json()
    assert data["product"]["product"]["quantity"] == 15

def test_add_product_quantity_zero_adjustment(client):
    post_response = client.post("/products", json={
        "product_name": "Tripod",
        "quantity": 20
    })
    product_id = post_response.json()["product"]["product"]["id"]

    add_response = client.post(f"/products/{product_id}/add", json={
        "adjustment": 0,
    })
    assert add_response.status_code == 422
    data = add_response.json()
    assert data["detail"][0]["msg"] == "Input should be greater than 0"

def test_add_product_quantity_negative_adjustment(client):
    post_response = client.post("/products", json={
        "product_name": "Lens",
        "quantity": 30
    })
    product_id = post_response.json()["product"]["product"]["id"]

    add_response = client.post(f"/products/{product_id}/add", json={
        "adjustment": -5,
    })
    assert add_response.status_code == 422

def test_add_product_quantity_not_found(client):
    response = client.post("/products/9999/add", json={
        "adjustment": 5,
    })
    assert response.status_code == 400

#--------------------------------------test order product--------------------------------------#

def test_order_product_success(client):
    post_response = client.post("/products", json={
        "product_name": "Speaker",
        "quantity": 25
    })
    product_id = post_response.json()["product"]["product"]["id"]

    order_response = client.post(f"/products/{product_id}/order", json={
        "quantity": 10
    })
    assert order_response.status_code == 200
    data = order_response.json()
    assert data["product"]["product"]["quantity"] == 15

def test_order_zero_quantity_fails(client):
    post_response = client.post("/products", json={
        "product_name": "SSD",
        "quantity": 18
    })
    product_id = post_response.json()["product"]["product"]["id"]

    order_response = client.post(f"/products/{product_id}/order", json={
        "quantity": 0
    })
    assert order_response.status_code == 422

def test_order_negative_quantity_fails(client):
    post_response = client.post("/products", json={
        "product_name": "RAM",
        "quantity": 22
    })
    product_id = post_response.json()["product"]["product"]["id"]

    order_response = client.post(f"/products/{product_id}/order", json={
        "quantity": -4
    })
    assert order_response.status_code == 422

def test_order_insufficient_stock_fails(client):
    post_response = client.post("/products", json={
        "product_name": "HDD",
        "quantity": 14
    })
    product_id = post_response.json()["product"]["product"]["id"]

    order_response = client.post(f"/products/{product_id}/order", json={
        "quantity": 20
    })
    assert order_response.status_code == 400
    data = order_response.json()
    assert data["error"] == "Insufficient stock. Available: 14, Requested: 20"

def test_order_product_not_found(client):
    response = client.post("/products/9999/order", json={
        "quantity": 5
    })
    assert response.status_code == 400

#--------------------------------------test delete product--------------------------------------#

def test_delete_product_success(client):
    post_response = client.post("/products", json={
        "product_name": "Router",
        "quantity": 9
    })
    product_id = post_response.json()["product"]["product"]["id"]

    delete_response = client.delete(f"/products/{product_id}")
    assert delete_response.status_code == 200

    data = delete_response.json()
    assert data["success"] is True

    check_response = client.get(f"/products/{product_id}")
    assert check_response.status_code == 404

def test_delete_product_not_found(client):
    response = client.delete("/products/9999")
    assert response.status_code == 500

#--------------------------------------test get all transactions--------------------------------------#

def test_get_all_transactions(client):
    post_response1 = client.post("/products", json={
        "product_name": "Orange",
        "quantity": 13
    })
    product_id1 = post_response1.json()["product"]["product"]["id"]

    post_response2 = client.post("/products", json={
        "product_name": "Apple",
        "quantity": 7
    })
    product_id2 = post_response2.json()["product"]["product"]["id"]

    client.post(f"/products/{product_id1}/add", json={
        "adjustment": 5
    })
    client.post(f"/products/{product_id2}/order", json={
        "quantity": 3
    })

    get_response = client.get("/transactions/")
    assert get_response.status_code == 200
    data = get_response.json()
    assert len(data) >= 3

def test_get_all_transactions_with_limit(client):
    get_response = client.get("/transactions/?limit=2")
    assert get_response.status_code == 200
    data = get_response.json()
    assert len(data) == 2

def test_transactions_deleted_on_product_deletion(client):
    post_response = client.post("/products", json={
        "product_name": "Banana",
        "quantity": 20
    })
    product_id = post_response.json()["product"]["product"]["id"]

    client.post(f"/products/{product_id}/add", json={
        "adjustment": 10
    })
    client.post(f"/products/{product_id}/order", json={
        "quantity": 5
    })

    delete_response = client.delete(f"/products/{product_id}")
    assert delete_response.status_code == 200

    get_response = client.get("/transactions/")
    assert get_response.status_code == 200
    data = get_response.json()
    assert all(txn["product_id"] != product_id for txn in data)

#--------------------------------------test get transactions--------------------------------------#

def test_get_transactions_by_product_success(client):
    post_response = client.post("/products", json={
        "product_name": "GPU",
        "quantity": 40
    })
    product_id = post_response.json()["product"]["product"]["id"]

    client.post(f"/products/{product_id}/add", json={
        "adjustment": 10
    })
    client.post(f"/products/{product_id}/order", json={
        "quantity": 5
    })

    get_response = client.get(f"/products/{product_id}/transactions")
    assert get_response.status_code == 200
    data = get_response.json()
    assert len(data) >= 2

def test_get_transactions_by_product_not_found(client):
    response = client.get("/products/9999/transactions")
    assert response.status_code == 404

#--------------------------------------test get inventory stats--------------------------------------#

def test_get_inventory_stats(client):
    client.post("/products", json={"product_name": "SSD", "quantity": 5})
    client.post("/products", json={"product_name": "HDD", "quantity": 0})

    response = client.get("/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["product_count"] >= 2
    assert data["total_stock"] >= 5
    assert data["database_size"] > 0

#--------------------------------------test backup database--------------------------------------#

def test_backup_database(client):
    response = client.post("/backup")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert os.path.exists(data["backup_path"])

#--------------------------------------test search products--------------------------------------#

def test_search_invalid_range(client):
    response = client.get("/search?min_quantity=10&max_quantity=5")
    assert response.status_code == 500

def test_search_products_by_name(client):
    client.post("/products", json={"product_name": "TFT", "quantity": 15})
    client.post("/products", json={"product_name": "Mousepad", "quantity": 25})

    response = client.get("/search?name=mou")
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_search_products_by_quantity_range(client):
    client.post("/products", json={"product_name": "Eraser", "quantity": 8})
    client.post("/products", json={"product_name": "Sharpner", "quantity": 18})

    response = client.get("/search?min_quantity=10&max_quantity=20")
    assert response.status_code == 200
    assert all(10 <= product["quantity"] <= 20 for product in response.json())

def test_search_instock_products(client):
    client.post("/products", json={"product_name": "Notebook", "quantity": 0})
    client.post("/products", json={"product_name": "Animal Book", "quantity": 12})

    response = client.get("/search?instock=true")
    assert response.status_code == 200
    assert all(product["quantity"] > 0 for product in response.json())

#--------------------------------------test bulk imports--------------------------------------#

def test_bulk_import_products_success(client):
    products = {
        "products": [
            {"product_name": "Plastic bottle", "quantity": 10},
            {"product_name": "Glass jar", "quantity": 20},
            {"product_name": "Ceramic jar", "quantity": 30}
        ]
    }
    response = client.post("/products/bulk_import", json=products)
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]["success"]) == 3
    assert len(data["results"]["failed"]) == 0

def test_bulk_import_products_with_errors(client):
    payload = {
        "products": [
            {"product_name": "Valid Product 1", "quantity": 5},
            {"product_name": "", "quantity": 10},  # Invalid name
            {"product_name": "Invalid Product 2", "quantity": -3},  # Negative quantity
            {"product_name": "Valid Product 3", "quantity": 0}
        ]
    }
    response = client.post("/products/bulk_import", json=payload)
    assert response.status_code == 422
    data = response.json()
    messages = [error["msg"] for error in data["detail"]]
    assert "String should have at least 1 character" in messages
    assert "Input should be greater than or equal to 0" in messages
