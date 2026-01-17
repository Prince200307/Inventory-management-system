import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

DB_FOLDER = "data"
DB_PATH = os.path.join(DB_FOLDER, "inventory.db")

@contextmanager
def get_db_connection():
    """
    Context manager for database connection with transaction support
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def setup_database():
    """
    Initialize database tables and indexes
    """
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Products table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT UNIQUE NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK (quantity >= 0)
        )
        """)
        # Transactions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            transaction_type TEXT NOT NULL,
            old_quantity INTEGER,
            new_quantity INTEGER,
            change_amount INTEGER,
            performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_name ON products(product_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transaction_product ON inventory_transactions(product_id)")

        print("Database setup completed successfully")

# ========== PRODUCT CRUD OPERATIONS ==========

def create_product(product_name: str, quantity: int) -> Dict[str, Any]:
    """
    Create a new product with initial quantity
    Returns the created product with its ID
    """
    if not product_name.isalnum():
        raise ValueError("Product name must contain only letters and numbers")

    if quantity < 0:
        raise ValueError("Quantity cannot be negative")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            # Insert product
            cursor.execute(
                "INSERT INTO products (product_name, quantity) VALUES (?, ?)",
                (product_name, quantity)
            )

            product_id = cursor.lastrowid

            # Log transaction
            log_transaction(cursor, product_id, "CREATE", None, quantity)

            # Return created product
            cursor.execute(
                "SELECT id, product_name, quantity, created_at, updated_at FROM products WHERE id = ?",
                (product_id,)
            )
            product = dict(cursor.fetchone())

            return {
                "success": True,
                "message": f"Product '{product_name}' created successfully",
                "product": product
            }

        except sqlite3.IntegrityError:
            raise ValueError(f"Product '{product_name}' already exists")

def get_all_products() -> List[Dict[str, Any]]:
    """
    Retrieve all products with their stock status
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, product_name, quantity, created_at, updated_at,
                   CASE
                       WHEN quantity = 0 THEN 'Out of Stock'
                       WHEN quantity < 5 THEN 'Low Stock'
                       ELSE 'In Stock'
                   END as stock_status
            FROM products
            ORDER BY product_name
        """)

        products = []
        for row in cursor.fetchall():
            product = dict(row)
            products.append(product)

        return products

def get_product_by_id(product_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a single product by ID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        )
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

def get_product_by_name(product_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a single product by name
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM products WHERE product_name = ?",
            (product_name,)
        )
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

def update_product_quantity(product_id: int, new_quantity: int) -> Dict[str, Any]:
    """
    Update product quantity to a specific value
    """
    if new_quantity < 0:
        raise ValueError("Quantity cannot be negative")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get current product
        cursor.execute(
            "SELECT id, quantity FROM products WHERE id = ?",
            (product_id,)
        )
        product = cursor.fetchone()

        if not product:
            raise ValueError(f"Product with ID {product_id} does not exist")

        old_quantity = product["quantity"]

        # Update product
        cursor.execute(
            "UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_quantity, product_id)
        )

        # Log transaction
        log_transaction(cursor, product_id, "UPDATE", old_quantity, new_quantity)

        # Return updated product
        cursor.execute(
            "SELECT id, product_name, quantity, created_at, updated_at FROM products WHERE id = ?",
            (product_id,)
        )
        updated_product = dict(cursor.fetchone())

        return {
            "success": True,
            "message": f"Product quantity updated from {old_quantity} to {new_quantity}",
            "product": updated_product
        }

def add_quantity_to_product(product_id: int, add_quantity: int) -> Dict[str, Any]:
    """
    Add quantity to existing product
    """
    if add_quantity <= 0:
        raise ValueError("Quantity to add must be positive")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get current product
        cursor.execute(
            "SELECT id, quantity FROM products WHERE id = ?",
            (product_id,)
        )
        product = cursor.fetchone()

        if not product:
            raise ValueError(f"Product with ID {product_id} does not exist")

        old_quantity = product["quantity"]
        new_quantity = old_quantity + add_quantity

        # Update product
        cursor.execute(
            "UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_quantity, product_id)
        )

        # Log transaction
        log_transaction(cursor, product_id, "ADD_QUANTITY", old_quantity, new_quantity)

        # Return updated product
        cursor.execute(
            "SELECT id, product_name, quantity, created_at, updated_at FROM products WHERE id = ?",
            (product_id,)
        )
        updated_product = dict(cursor.fetchone())

        return {
            "success": True,
            "message": f"Added {add_quantity} to product. New quantity: {new_quantity}",
            "product": updated_product
        }

def order_product(product_id: int, order_quantity: int) -> Dict[str, Any]:
    """
    Reduce product quantity (place an order)
    """
    if order_quantity <= 0:
        raise ValueError("Order quantity must be positive")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get current product
        cursor.execute(
            "SELECT id, quantity FROM products WHERE id = ?",
            (product_id,)
        )
        product = cursor.fetchone()

        if not product:
            raise ValueError(f"Product with ID {product_id} does not exist")

        old_quantity = product["quantity"]

        # Check stock availability
        if order_quantity > old_quantity:
            raise ValueError(f"Insufficient stock. Available: {old_quantity}, Requested: {order_quantity}")

        new_quantity = old_quantity - order_quantity

        # Update product
        cursor.execute(
            "UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_quantity, product_id)
        )

        # Log transaction
        log_transaction(cursor, product_id, "ORDER", old_quantity, new_quantity)

        # Return updated product
        cursor.execute(
            "SELECT id, product_name, quantity, created_at, updated_at FROM products WHERE id = ?",
            (product_id,)
        )
        updated_product = dict(cursor.fetchone())

        return {
            "success": True,
            "message": f"Order successful. Remaining quantity: {new_quantity}",
            "product": updated_product,
            "ordered_quantity": order_quantity
        }

def delete_product(product_id: int) -> Dict[str, Any]:
    """
    Delete a product and all its transactions
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get product before deletion
        cursor.execute(
            "SELECT product_name FROM products WHERE id = ?",
            (product_id,)
        )
        product = cursor.fetchone()

        if not product:
            raise ValueError(f"Product with ID {product_id} does not exist")

        product_name = product["product_name"]

        # Delete product (transactions will be deleted automatically due to CASCADE)
        cursor.execute(
            "DELETE FROM products WHERE id = ?",
            (product_id,)
        )

        return {
            "success": True,
            "message": f"Product '{product_name}' deleted successfully"
        }

# ========== TRANSACTION OPERATIONS ==========

def log_transaction(cursor, product_id: int, transaction_type: str,
                    old_quantity: Optional[int], new_quantity: int) -> None:
    """
    Log inventory transaction for audit trail
    """
    change_amount = new_quantity - (old_quantity if old_quantity is not None else 0)

    cursor.execute("""
        INSERT INTO inventory_transactions
        (product_id, transaction_type, old_quantity, new_quantity, change_amount)
        VALUES (?, ?, ?, ?, ?)
    """, (product_id, transaction_type, old_quantity, new_quantity, change_amount))

def get_all_transactions(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get all transactions with product details
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                t.id,
                p.product_name,
                t.transaction_type,
                t.old_quantity,
                t.new_quantity,
                t.change_amount,
                t.performed_at
            FROM inventory_transactions t
            JOIN products p ON t.product_id = p.id
            ORDER BY t.performed_at DESC
            LIMIT ?
        """, (limit,))

        transactions = []
        for row in cursor.fetchall():
            transaction = dict(row)
            transactions.append(transaction)

        return transactions

def get_transactions_by_product(product_id: int) -> List[Dict[str, Any]]:
    """
    Get all transactions for a specific product
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                t.id,
                p.product_name,
                t.transaction_type,
                t.old_quantity,
                t.new_quantity,
                t.change_amount,
                t.performed_at
            FROM inventory_transactions t
            JOIN products p ON t.product_id = p.id
            WHERE t.product_id = ?
            ORDER BY t.performed_at DESC
        """, (product_id,))

        transactions = []
        for row in cursor.fetchall():
            transaction = dict(row)
            transactions.append(transaction)

        return transactions

# ========== DATABASE UTILITIES ==========

def backup_database() -> str:
    """
    Create a timestamped backup of the database
    Returns the backup file path
    """
    import shutil
    import datetime

    backup_folder = os.path.join(DB_FOLDER, "backups")
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_folder, f"inventory_backup_{timestamp}.db")

    try:
        # Ensure all connections are closed
        shutil.copy2(DB_PATH, backup_path)
        return backup_path
    except Exception as e:
        raise RuntimeError(f"Failed to create backup: {str(e)}")

def get_database_stats() -> Dict[str, Any]:
    """
    Get database statistics
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Count products
        cursor.execute("SELECT COUNT(*) as product_count FROM products")
        product_count = cursor.fetchone()["product_count"]

        # Count transactions
        cursor.execute("SELECT COUNT(*) as transaction_count FROM inventory_transactions")
        transaction_count = cursor.fetchone()["transaction_count"]

        # Total stock
        cursor.execute("SELECT SUM(quantity) as total_stock FROM products")
        total_stock = cursor.fetchone()["total_stock"] or 0

        # Out of stock products
        cursor.execute("SELECT COUNT(*) as out_of_stock_count FROM products WHERE quantity = 0")
        out_of_stock_count = cursor.fetchone()["out_of_stock_count"]

        return {
            "product_count": product_count,
            "transaction_count": transaction_count,
            "total_stock": total_stock,
            "out_of_stock_count": out_of_stock_count,
            "database_path": DB_PATH,
            "database_size": os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        }