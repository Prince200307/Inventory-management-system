import pytest
from fastapi.testclient import TestClient

from main import app

test_client = TestClient(app)

@pytest.fixture
def valid_product_payload():
    return {
        "product_name": "Notebook",
        "quantity": 50
    }


@pytest.fixture
def mock_database_layer(monkeypatch):
    """
    Mock database functions with EXACT return formats
    matching database.py
    """

    def mock_create_product(product_name, quantity):
        return {
            "success": True,
            "message": f"Product '{product_name}' created successfully",
            "product": {
                "id": 1,
                "product_name": product_name,
                "quantity": quantity,
                "created_at": "2026-01-01 10:00:00",
                "updated_at": "2026-01-01 10:00:00"
            }
        }

    def mock_get_all_products():
        return [
            {
                "id": 1,
                "product_name": "Notebook",
                "quantity": 50,
                "created_at": "2026-01-01 10:00:00",
                "updated_at": "2026-01-01 10:00:00",
                "stock_status": "In Stock"
            }
        ]

    def mock_get_product_by_id(product_id):
        if product_id == 1:
            return {
                "id": 1,
                "product_name": "Notebook",
                "quantity": 50,
                "created_at": "2026-01-01 10:00:00",
                "updated_at": "2026-01-01 10:00:00"
            }
        return None

    def mock_update_product_quantity(product_id, new_quantity):
        return {
            "success": True,
            "message": "Product quantity updated",
            "product": {
                "id": product_id,
                "product_name": "Notebook",
                "quantity": new_quantity,
                "created_at": "2026-01-01 10:00:00",
                "updated_at": "2026-01-02 10:00:00"
            }
        }

    def mock_add_quantity_to_product(product_id, add_quantity):
        return {
            "success": True,
            "message": "Added quantity",
            "product": {
                "id": product_id,
                "product_name": "Notebook",
                "quantity": 50 + add_quantity,
                "created_at": "2026-01-01 10:00:00",
                "updated_at": "2026-01-02 10:00:00"
            }
        }

    def mock_order_product(product_id, order_quantity):
        return {
            "success": True,
            "message": "Order successful",
            "product": {
                "id": product_id,
                "product_name": "Notebook",
                "quantity": 50 - order_quantity,
                "created_at": "2026-01-01 10:00:00",
                "updated_at": "2026-01-02 10:00:00"
            },
            "ordered_quantity": order_quantity
        }

    def mock_delete_product(product_id):
        return {
            "success": True,
            "message": "Product 'Notebook' deleted successfully"
        }

    def mock_get_all_transactions(limit=50):
        return [
            {
                "id": 1,
                "product_id": 1,
                "product_name": "Notebook",
                "transaction_type": "CREATE",
                "old_quantity": 0,
                "new_quantity": 50,
                "change_amount": 50,
                "performed_at": "2026-01-01 10:00:00"
            }
        ]

    def mock_get_transactions_by_product(product_id):
        return mock_get_all_transactions()

    def mock_get_database_stats():
        return {
            "product_count": 1,
            "transaction_count": 1,
            "total_stock": 50,
            "out_of_stock_count": 0,
            "database_path": "data/inventory.db",
            "database_size": 1024
        }

    def mock_backup_database():
        return "data/backups/inventory_backup_20260101.db"

    monkeypatch.setattr("main.database.create_product", mock_create_product)
    monkeypatch.setattr("main.database.get_all_products", mock_get_all_products)
    monkeypatch.setattr("main.database.get_product_by_id", mock_get_product_by_id)
    monkeypatch.setattr("main.database.update_product_quantity", mock_update_product_quantity)
    monkeypatch.setattr("main.database.add_quantity_to_product", mock_add_quantity_to_product)
    monkeypatch.setattr("main.database.order_product", mock_order_product)
    monkeypatch.setattr("main.database.delete_product", mock_delete_product)
    monkeypatch.setattr("main.database.get_all_transactions", mock_get_all_transactions)
    monkeypatch.setattr("main.database.get_transactions_by_product", mock_get_transactions_by_product)
    monkeypatch.setattr("main.database.get_database_stats", mock_get_database_stats)
    monkeypatch.setattr("main.database.backup_database", mock_backup_database)


def test_root_endpoint():
    response = test_client.get("/")
    assert response.status_code == 200


def test_health_check(mock_database_layer):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_product_success(valid_product_payload, mock_database_layer):
    response = test_client.post("/products", json=valid_product_payload)

    assert response.status_code == 201
    assert response.json()["product"]["success"] is True
    assert response.json()["product"]["product"]["product_name"] == "Notebook"


@pytest.mark.parametrize(
    "payload",
    [
        {"product_name": "", "quantity": 10},
        {"product_name": "Bad@Name", "quantity": 10},
        {"product_name": "Notebook", "quantity": -1},
        {"quantity": 10},
        {"product_name": "Notebook"},
    ]
)
def test_create_product_invalid_inputs(payload):
    response = test_client.post("/products", json=payload)
    assert response.status_code == 422


def test_get_all_products(mock_database_layer):
    response = test_client.get("/products/")
    assert response.status_code == 200
    assert response.json()[0]["stock_status"] == "In Stock"


def test_get_product_by_id(mock_database_layer):
    response = test_client.get("/products/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_update_product_quantity(mock_database_layer):
    response = test_client.put("/products/1/quantity", json={"quantity": 100})
    assert response.status_code == 200
    assert response.json()["product"]["product"]["quantity"] == 100


def test_add_product_quantity(mock_database_layer):
    response = test_client.post("/products/1/add", json={"adjustment": 10})
    assert response.status_code == 200
    assert response.json()["product"]["product"]["quantity"] == 60


def test_order_product(mock_database_layer):
    response = test_client.post("/products/1/order", json={"quantity": 20})
    assert response.status_code == 200
    assert response.json()["product"]["ordered_quantity"] == 20


def test_delete_product(mock_database_layer):
    response = test_client.delete("/products/1")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_get_transactions(mock_database_layer):
    response = test_client.get("/transactions/")
    assert response.status_code == 200
    assert response.json()[0]["transaction_type"] == "CREATE"


def test_get_stats(mock_database_layer):
    response = test_client.get("/stats")
    assert response.status_code == 200
    assert response.json()["product_count"] == 1


def test_backup_database(mock_database_layer):
    response = test_client.post("/backup")
    assert response.status_code == 200
    assert "backup" in response.json()["backup_path"]
